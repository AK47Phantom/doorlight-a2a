"""Local service adapters used by Doorlight agents.

These are deliberately real, testable operations over the retained synthetic
packet—not empty tool names. Each function is read-only and suitable for the
Zone 3 audit layer. Production adapters would implement the same functions
against an OCR provider, policy repository, document store, or transaction API.
"""
from __future__ import annotations
import hashlib
import re
from collections import Counter
from .agents.base import citation

def transaction_snapshot(transaction: dict) -> dict:
    return {key: transaction[key] for key in ("id", "property", "side", "type", "financing", "jurisdiction", "closingDate", "parties", "importantDates")}

def search_documents(transaction: dict, queries: list[str]) -> list[dict]:
    terms = [term.lower() for term in queries]
    return [document for document in transaction["documents"] if any(term in f"{document['name']} {document['text']}".lower() for term in terms)]

def classify_document(document: dict) -> str:
    name = document["name"].lower()
    rules = {"purchase agreement": "Controlling agreement", "amendment": "Amendment", "counteroffer": "Offer negotiation", "deposit": "Escrow evidence", "title": "Title evidence", "disclosure": "Statutory disclosure", "financing": "Financing evidence", "contingency": "Contingency evidence"}
    return next((category for term, category in rules.items() if term in name), "Supporting transaction record")

def source_fingerprint(document: dict) -> str:
    raw = f"{document['name']}|{document['version']}|{document['page']}|{document['text']}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def document_metadata(document: dict) -> dict:
    return {"citation": citation(document), "classification": classify_document(document), "hash": source_fingerprint(document), "controlling": bool(document.get("controlling")), "characters": len(document["text"])}

def duplicate_or_version_gaps(documents: list[dict]) -> list[str]:
    counts = Counter(document["name"] for document in documents)
    notes = [f"Possible duplicate record: {name}" for name, count in counts.items() if count > 1]
    return notes or ["No duplicate document names detected in the retained packet."]

def extract_facts(document: dict) -> list[dict]:
    """Small deterministic extractor; claims remain traceable to the exact document."""
    text = document["text"]
    patterns = [(r"(?:Purchase price|purchase consideration) \$([\d,]+(?:\.\d{2})?)", "purchase_price"), (r"closing date(?: is| remains| is amended to| to)? ([A-Z][A-Za-z]+ \d{1,2},? \d{4})", "closing_date"), (r"(Buyer|Seller) signature (present|missing)", "signature_status")]
    facts=[]
    extraction_metadata = {"region": "Synthetic source page body", "confidence": 1.0, "extractor": "Doorlight Evidence Extractor 1.0"}
    for pattern, kind in patterns:
        for match in re.finditer(pattern, text, re.I): facts.append({"kind": kind, "value": " ".join(match.groups()), "citation": citation(document), **extraction_metadata})
    material_phrases = ("seller signature missing", "remains pending confirmation from escrow", "requires written payoff or release evidence", "no superseding amendment resolves")
    for phrase in material_phrases:
        if phrase in text.lower():
            sentence = next((part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if phrase in part.lower()), phrase)
            facts.append({"kind": "exception_language", "value": sentence, "citation": citation(document, phrase), **extraction_metadata})
    return facts

def select_policy(transaction: dict) -> dict:
    policy = transaction["policyContext"]
    return {"id": policy["policyId"], "version": policy["version"], "requirements": policy["checklist"], "basis": [transaction["jurisdiction"], transaction["side"], transaction["type"], transaction["financing"]]}

def compare_material_terms(documents: list[dict]) -> list[dict]:
    agreement = next((d for d in documents if d["name"] == "Purchase Agreement"), None)
    counteroffer = next((d for d in documents if d["name"] == "Counteroffer"), None)
    exceptions=[]
    price = re.compile(r"(?:Purchase price|purchase consideration) \$([\d,]+(?:\.\d{2})?)", re.I)
    agreement_price = price.search(agreement["text"]) if agreement else None
    counter_price = price.search(counteroffer["text"]) if counteroffer else None
    if agreement and counteroffer and agreement_price and counter_price and agreement_price.group(1) != counter_price.group(1):
        exceptions.append({"kind": "price_conflict", "detail": f"{citation(agreement, agreement_price.group(0))} states ${agreement_price.group(1)} while {citation(counteroffer, counter_price.group(0))} states ${counter_price.group(1)}; no accepted superseding record resolves the difference.", "evidence": [citation(agreement, agreement_price.group(0)), citation(counteroffer, counter_price.group(0))]})
    return exceptions

def requirement_status(transaction: dict, requirement: str) -> tuple[str, list[str]]:
    documents = transaction["documents"]
    packet_text = " ".join(document["text"].lower() for document in documents)

    def named(*names: str) -> list[dict]:
        wanted = {name.lower() for name in names}
        return [document for document in documents if document["name"].lower() in wanted]

    def citations(records: list[dict]) -> list[str]:
        return [citation(document) for document in records]

    agreement = named("Purchase Agreement")
    agency = named("Agency Disclosure")
    deposit = named("Deposit Receipt")
    financing = named("Financing Approval", "Financing Preapproval")
    disclosures = named("Seller Property Disclosure", "Natural Hazard Disclosure")
    title = named("Preliminary Title Report")
    contingency = named("Inspection Contingency Removal")
    closing = named("Closing Disclosure Draft")

    mapping = {
        "Executed agreement": (
            "SATISFIED" if agreement and "buyer and seller signatures present" in packet_text and "seller signature missing" not in packet_text else "PARTIAL",
            citations(agreement),
        ),
        "Agency disclosure": (
            "SATISFIED" if agency and "buyer and brokerage acknowledgments are present" in agency[0]["text"].lower() else "MISSING",
            citations(agency),
        ),
        "Deposit confirmation": (
            "SATISFIED" if deposit and "confirmed by escrow" in deposit[0]["text"].lower() else "PARTIAL",
            citations(deposit),
        ),
        "Financing evidence": (
            "SATISFIED" if financing and any("lender" in document["text"].lower() for document in financing) else "MISSING",
            citations(financing),
        ),
        "Seller and hazard disclosures": (
            "SATISFIED" if len(disclosures) == 2 and all("acknowledgment" in document["text"].lower() for document in disclosures) else "PARTIAL",
            citations(disclosures),
        ),
        "Clear title path": (
            "MISSING" if "requires written payoff" in packet_text else "SATISFIED",
            citations(title),
        ),
        "Contingency disposition": (
            "SATISFIED" if contingency and "signed before the recorded deadline" in contingency[0]["text"].lower() else "MISSING",
            citations(contingency),
        ),
        "Closing authorization": (
            "HUMAN_JUDGMENT_REQUIRED",
            citations(closing),
        ),
    }
    return mapping.get(requirement, ("HUMAN_JUDGMENT_REQUIRED", []))
