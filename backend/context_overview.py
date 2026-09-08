"""Derived Context Overview built from retained pages by small, auditable extractors."""
from __future__ import annotations
import re
from .agents.base import citation


def _find(transaction: dict, name: str) -> dict | None:
    return next((document for document in transaction["documents"] if document["name"] == name), None)


def _extract(document: dict | None, patterns: list[tuple[str, str]]) -> list[dict]:
    if not document:
        return []
    output = []
    for label, pattern in patterns:
        match = re.search(pattern, document["text"], re.I)
        if match:
            output.append({"label": label, "value": match.group(1).strip(), "citation": citation(document, match.group(0))})
    return output


def build_context_overview(transaction: dict) -> dict:
    """Return only fields found by document-specific extraction tools with citations."""
    agreement = _find(transaction, "Purchase Agreement")
    amendment = _find(transaction, "Amendment #1")
    escrow = _find(transaction, "Escrow Instructions")
    finance = _find(transaction, "Financing Approval") or _find(transaction, "Financing Preapproval")
    loan_estimate = _find(transaction, "Loan Estimate")
    title = _find(transaction, "Preliminary Title Report")
    disclosures = [_find(transaction, "Seller Property Disclosure"), _find(transaction, "Natural Hazard Disclosure")]
    supplemental_names = ["Agent Visual Inspection Disclosure", "Seller Property Questionnaire", "Lead-Based Paint Applicability Notice", "Fire Hazard Severity Zone Notice", "Mello-Roos and 1915 Act Notice", "HOA and Common Interest Applicability", "Local and Property System Applicability", "Pest and Wood-Destroying Organism Report", "Insurance and Flood Evaluation", "Lender Conditions List", "Estimated Closing Statement", "Seller Withholding and Vesting Review", "Possession and Repair Confirmation", "Closing Disclosure Draft"]
    supplemental = [_find(transaction, name) for name in supplemental_names]

    sections = [
        {"title": "Parties & Contract", "method": "Agreement field extractor", "items": _extract(agreement, [
            ("Buyer", r"identifies ([A-Za-z ]+) as buyer"), ("Seller", r"as buyer and ([A-Za-z ]+) as seller"),
            ("Property / APN", r"seller for (.+?APN [\d-]+)\."), ("Purchase price", r"Purchase price (\$[\d,]+)"),
            ("Deposit", r"earnest-money deposit (\$[\d,]+)"), ("Execution", r"(buyer and seller signatures present|Seller signature missing)")])},
        {"title": "Dates & Controlling Terms", "method": "Agreement/amendment date extractor", "items": _extract(amendment, [
            ("Controlling closing date", r"(?:date remains|date to) ([A-Z][a-z]+ \d{1,2}, \d{4})"),
            ("Amendment effect", r"(No [^.]+ is changed\.|No [^.]+ is changed\.)")]) + [{"label": "Source relationship", "value": "Agreement and later amendment are retained as separate, versioned pages.", "citation": citation(agreement) if agreement else "No agreement source"}]},
        {"title": "Escrow & Funds", "method": "Escrow/deposit passage extractor", "items": _extract(escrow, [
            ("Escrow holder", r"opened with ([^.]+)\."), ("Escrow purpose", r"(Written instructions require[^.]+\.)")]) + _extract(_find(transaction, "Deposit Receipt"), [
            ("Deposit status", r"((?:Earnest money receipt|The buyer-side file)[^.]+\.)")])},
        {"title": "Financing & Closing Figures", "method": "Lender/Loan Estimate extractor", "items": _extract(finance, [
            ("Lender evidence", r"([^.]+(?:approval|preapproval)[^.]+\.)")]) + _extract(loan_estimate, [
            ("Estimated loan amount", r"loan amount(?: of)? (\$[\d,]+(?:\.\d{2})?)(?:,|;)"), ("Closing-figure control", r"((?:Rate-lock|Lock:)[^.]+\.)")])},
        {"title": "Title, Disclosures & Conditions", "method": "Title/disclosure exception extractor", "items": _extract(title, [
            ("Title finding", r"([^.]+(?:lien exception|title report)[^.]+\.)")]) + [
                {"label": document["name"], "value": "Delivered source retained for review." if "delivered" in document["text"].lower() else "Source retained; review wording.", "citation": citation(document)}
                for document in disclosures if document
            ]},
        {"title": "Conditional & Supplemental Reviews", "method": "Document passage splitter", "items": [
            {"label": document["name"], "value": document["text"].split(".")[0] + ".", "citation": citation(document)}
            for document in supplemental if document
        ]},
    ]
    return {"caseId": transaction["id"], "generatedBy": "Document-specific regex extractors with page citations; no case fields are displayed until derived from a retained document.", "sections": sections}
