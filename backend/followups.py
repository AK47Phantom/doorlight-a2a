"""Bounded, source-aware answers for conversational questions after a workflow run."""
from __future__ import annotations

import re
from difflib import get_close_matches
from .agents.base import citation

STOP_WORDS = {"a", "an", "and", "are", "about", "can", "could", "do", "does", "for", "from", "how", "i", "is", "it", "me", "of", "on", "or", "please", "the", "this", "to", "what", "which", "why", "with", "you"}
AGENT_SCOPE = {
    "transaction-intake-agent": "The Transaction Intake Agent organizes case details and timeline information; it does not decide legal validity or closing readiness.",
    "policy-agent": "The Policy & Rules Agent explains the selected review checklist and its limits; it does not make the final risk decision.",
    "document-intake-agent": "The Document Intake Agent explains retained records, versions, and the limits of intake review.",
    "evidence-agent": "The Evidence Agent provides what retained records say with quotes and citations; it does not make a legal conclusion.",
    "reconciliation-agent": "The Reconciliation Agent compares related records and identifies unresolved differences; it does not choose the risk lane.",
    "compliance-agent": "The Compliance Agent explains checklist evidence and gaps; it does not provide legal advice or choose the risk lane.",
    "risk-agent": "The Risk Agent explains the readiness recommendation, decisive evidence, and the next review step.",
    "orchestrator": "Light can explain the transaction, the agents, and the retained evidence in plain English.",
}
AGENT_EXPLANATION = {
    "transaction-intake-agent": "The Transaction Intake Agent turns the raw case packet into an organized starting record: people, property, transaction type, financing, and dates.",
    "policy-agent": "The Policy & Rules Agent selects the supplied review checklist that fits this transaction. It does not decide whether the transaction passes it.",
    "document-intake-agent": "The Document Intake Agent inventories source records, identifies versions, and records what was received. It does not decide whether a document proves a requirement.",
    "evidence-agent": "The Evidence Agent searches retained records and reports exactly what they say with page citations. It does not make a compliance or risk decision.",
    "reconciliation-agent": "The Reconciliation Agent compares related records to identify the controlling document and unresolved differences.",
    "compliance-agent": "The Compliance Agent checks each supplied requirement against available evidence and marks the evidence status. It does not give legal advice or choose the risk color.",
    "risk-agent": "The Risk Agent combines the completed evidence and checklist review into one Green, Amber, or Red readiness recommendation.",
}
AGENT_DETAILS = {
    "transaction-intake-agent": {
        "name": "Transaction Intake Agent",
        "does": "Creates one clean starting record from the selected case, including the people, property, financing, and timeline.",
        "can": "Explain the transaction basics, parties, dates, property details, and what information has been supplied.",
        "tools": ("transaction lookup", "party normalizer", "milestone reader"),
    },
    "policy-agent": {
        "name": "Policy & Rules Agent",
        "does": "Selects the supplied Doorlight review checklist that fits the transaction type, location, side, and financing.",
        "can": "Explain which checklist is being used and why a requirement belongs in the review.",
        "tools": ("policy search", "checklist selector"),
    },
    "document-intake-agent": {
        "name": "Document Intake Agent",
        "does": "Inventories the retained records, identifies their versions, and keeps their source information organized.",
        "can": "Explain which documents are in the packet, what version is retained, and the limits of the visual/OCR intake preview.",
        "tools": ("retained text reader", "document classifier", "version registry", "source hasher", "metadata extractor", "vision/OCR preflight"),
    },
    "evidence-agent": {
        "name": "Evidence Agent",
        "does": "Finds exactly what the retained documents say and ties each important statement to a document and page.",
        "can": "Answer source questions about prices, signatures, deposits, title items, dates, disclosures, and other recorded facts.",
        "tools": ("document search", "evidence retrieval", "citation builder"),
    },
    "reconciliation-agent": {
        "name": "Reconciliation Agent",
        "does": "Places agreements, amendments, and counteroffers in order and compares terms that may conflict.",
        "can": "Explain which record controls a term, what does not match, and what evidence is still needed to resolve a difference.",
        "tools": ("agreement chain builder", "term comparator", "signature checker", "title exception search", "commission term reader"),
    },
    "compliance-agent": {
        "name": "Compliance Agent",
        "does": "Checks each supplied review requirement against the retained evidence and labels the evidence as supported, partial, missing, or needing human judgment.",
        "can": "Explain the checklist, the evidence behind each item, and what is still missing from the packet.",
        "tools": ("checklist tool", "policy search", "document search", "evidence retrieval", "requirement evaluator"),
    },
    "risk-agent": {
        "name": "Risk Agent",
        "does": "Reviews the completed evidence and checklist results and makes the Green, Amber, or Red readiness recommendation.",
        "can": "Explain the recommendation, the decisive blockers or open items, what would change the recommendation, and the next review step.",
        "tools": ("risk rubric", "material blocker search", "administrative gap search", "recommendation validator"),
    },
}
AGENT_METHODS = {
    "transaction-intake-agent": "First, it opens the selected case record and identifies the people, property, financing type, and supplied dates. Next, it standardizes names and roles so later agents do not treat the same person or date as separate facts. Then, it builds one starting timeline from the information already in the case. Finally, it gives that organized starting record to the Policy and Document Intake Agents. It does not perform document OCR.",
    "policy-agent": "First, it reads the transaction type, location, side, and financing details from Intake. Next, it searches the supplied Doorlight policy library for the matching review scope. Then, it selects the checklist requirements that later agents need to test. Finally, it passes that checklist to Compliance; it does not decide whether the evidence satisfies it.",
    "document-intake-agent": "First, it opens each retained source page and identifies the kind of record it appears to be. Next, it runs the local vision/OCR preflight when enabled and records the readable page text. Then, it records the document version, source fingerprint, and basic metadata so later agents can distinguish one record from another. Finally, it creates an organized inventory for Evidence and Reconciliation; it does not decide legal meaning.",
    "evidence-agent": "First, it receives a question or a required fact from the workflow. Next, it searches the retained page text and retrieves the relevant surrounding passage rather than relying on a short label. Then, it attaches the document name, version, and page to the exact statement it found. Finally, it passes those cited facts to Reconciliation and Compliance without turning them into a legal conclusion.",
    "reconciliation-agent": "First, it places the purchase agreement, amendments, and counteroffers in the order described by the documents. Next, it compares the parties, property, price, signatures, dates, and title-related terms across those records. Then, it identifies which record appears to control a term and flags anything the records do not clearly resolve. Finally, it passes the conflict list and controlling chain to Compliance and Risk.",
    "compliance-agent": "First, it takes the checklist chosen by Policy. Next, it evaluates one requirement at a time against the cited evidence and reconciliation results. Then, it records a limited status—supported, partial, missing, or requiring human judgment—so missing proof is never treated as proof of completion. Finally, it sends the item-by-item review to Risk; it does not provide legal advice or choose a color.",
    "risk-agent": "First, it reads the completed evidence, reconciliation, and checklist results together. Next, it checks for material blockers, unresolved conflicts, and open administrative items. Then, it forms one Green, Amber, or Red recommendation and validates that the reasons are tied to the retained evidence. Finally, it gives Light the recommendation, cited reasons, and next review step; Amber and Red require human review in this demo.",
}
GENERAL = {
    "escrow": "Escrow is a neutral settlement process that holds documents and funds under the parties' written instructions. It does not make the buyer's or seller's legal decisions.",
    "contingen": "A contingency is a contractual condition that gives a party time to investigate or confirm something, such as financing, appraisal, inspection, or title. Whether it has been removed depends on the signed transaction records.",
    "title insurance": "Title insurance protects against certain covered title problems under the issued policy. A preliminary title report is not the final policy and can list exceptions that still need review.",
    "disclosure": "A disclosure is information delivered for review, often from a seller, agent, provider, or public source. Receipt of a disclosure does not prove that a condition is absent or that a buyer has waived investigation.",
    "earnest money": "Earnest money is the buyer's initial deposit toward the purchase. A transfer request or delivery reference is different from an escrow confirmation that funds were received and posted.",
    "appraisal": "An appraisal is a professional opinion of value prepared for its intended use. An appraisal notice or lender review note is not a substitute for the complete appraisal report.",
    "preapproval": "A preapproval is an early lender assessment based on the information reviewed at that point. It is not a clear-to-close or a guarantee that the lender will fund.",
    "clear to close": "A clear-to-close is the lender's authorization to prepare the loan for closing after its required review. It is still separate from funding, recording, and delivery of possession.",
    "closing cost": "Closing costs are the transaction charges and prepaid items shown by the lender and settlement professionals. Who pays a particular charge depends on the accepted agreement, lender rules, local practice, and the final settlement records.",
    "counteroffer": "A counteroffer proposes different terms and normally requires acceptance before it becomes part of the agreement. A prior offer and a counteroffer should be compared carefully so no one assumes the wrong price or deadline controls.",
    "inspection": "A home inspection is an investigation of accessible conditions at a point in time. It is different from a guarantee, a specialist inspection, an appraisal, or a decision about whether the parties will agree to repairs.",
    "mortgage": "A mortgage loan is the lender's financing for the purchase. Preapproval, final approval, clear-to-close, funding, and recording are separate milestones, so one should not be mistaken for another.",
    "insurance": "Homeowners insurance evidence identifies proposed coverage, limits, dates, and mortgagee information. A quote or binder is not the same as a broad guarantee that every loss will be covered.",
    "lien": "A lien is a recorded claim or interest that can affect title. Whether it must be paid, released, insured over, or otherwise resolved depends on the title and settlement professionals' review of the specific record.",
}

def _sentence(document: dict, terms: list[str]) -> tuple[str, str]:
    for sentence in re.split(r"(?<=[.!?])\s+", document["text"]):
        if any(term in sentence.lower() for term in terms):
            return sentence.strip(), citation(document, sentence)
    text = document["text"].split("\n\n", 1)[0].replace("\n", " ").strip()
    return text[:360].rstrip() + ("…" if len(text) > 360 else ""), citation(document)

def _relevant_documents(question: str, transaction: dict, limit: int = 3) -> list[dict]:
    terms = [token for token in re.findall(r"[a-z]{3,}", question.lower()) if token not in STOP_WORDS]
    def score(document: dict) -> int:
        haystack = f"{document['name']} {document['text']}".lower()
        return sum(haystack.count(term) for term in terms)
    return [document for document in sorted(transaction["documents"], key=score, reverse=True) if score(document)][:limit]

def _document(transaction: dict, name: str) -> dict:
    return next(item for item in transaction["documents"] if item["name"] == name)

def _agent_overview(agent_id: str, transaction: dict, artifact: dict, direct: bool) -> str:
    detail = AGENT_DETAILS[agent_id]
    tools = "; ".join(detail["tools"])
    # An overview requested through Light must never look like the specialist
    # took over the conversation. Direct specialist mode is the only place
    # where the specialist speaks for its own case result.
    heading = f"{detail['name']} — Case {transaction['id']}" if direct else f"Light's Overview: {detail['name']}"
    completed = ""
    if direct and agent_id == "compliance-agent":
        evaluations = artifact.get("evaluations", [])
        open_items = [f"{item['requirement']}: {item['status']}" for item in evaluations if item.get("status") != "SATISFIED"]
        completed = f" In this case, the checklist found: {'; '.join(open_items[:4]) or 'no non-supported item in the returned checklist'}."
    elif direct and agent_id == "document-intake-agent":
        completed = f" In this case, it inventoried {len(artifact.get('inventory', []))} retained records."
    elif direct and agent_id == "risk-agent":
        completed = f" In this case, its current recommendation is {artifact.get('lane', 'not yet rated')}."
    elif direct:
        summary = str(artifact.get("summary", "a validated specialist result")).rstrip(".")
        completed = f" In this case, it returned: {summary}."
    return (
        f"{heading}\n\n"
        f"What it does: {detail['does']}\n\n"
        f"How it works, in order: {AGENT_METHODS[agent_id]}\n\n"
        f"What it can answer: {detail['can']}\n\n"
        f"Tools it uses: {tools}.{completed}\n\n"
        f"Important limit: {AGENT_SCOPE[agent_id]}"
    )

def _mentioned_agent(question: str) -> str | None:
    aliases = {
        "transaction-intake-agent": ("transaction intake", "intake agent"),
        "policy-agent": ("policy agent", "policy & rules", "policy and rules", "rules agent"),
        "document-intake-agent": ("document intake", "document agent"),
        "evidence-agent": ("evidence agent",),
        "reconciliation-agent": ("reconciliation agent", "reconcile agent"),
        "compliance-agent": ("compliance agent", "compliance"),
        "risk-agent": ("risk agent",),
    }
    lowered = question.lower()
    direct_match = next((agent_id for agent_id, phrases in aliases.items() if any(phrase in lowered for phrase in phrases)), None)
    if direct_match:
        return direct_match

    # People naturally abbreviate and misspell these longer agent names in a
    # chat. Match recognisable stems first, then a close single-word spelling.
    stems = {
        "transaction-intake-agent": ("transaction", "intake"),
        "policy-agent": ("policy", "rule"),
        "document-intake-agent": ("document",),
        "evidence-agent": ("evidence",),
        "reconciliation-agent": ("reconcil",),
        "compliance-agent": ("compliance",),
        "risk-agent": ("risk",),
    }
    tokens = re.findall(r"[a-z]+", lowered)
    for agent_id, agent_stems in stems.items():
        if any(any(stem in token for stem in agent_stems) for token in tokens):
            return agent_id
    canonical = {"transaction": "transaction-intake-agent", "intake": "transaction-intake-agent", "policy": "policy-agent", "document": "document-intake-agent", "evidence": "evidence-agent", "reconciliation": "reconciliation-agent", "compliance": "compliance-agent", "risk": "risk-agent"}
    for token in tokens:
        close = get_close_matches(token, canonical, n=1, cutoff=0.76)
        if close:
            return canonical[close[0]]
    return None

def is_agent_overview_question(question: str) -> bool:
    """Whether a short request is asking Light to explain an agent, not run it."""
    normalized = re.sub(r"\bwt\b", "what", question.lower())
    normalized = re.sub(r"\babt\b", "about", normalized)
    mentioned = _mentioned_agent(normalized)
    if not mentioned:
        return False
    # A reason for a colour is a transaction question, even though it names
    # the Risk Agent's subject area.
    if any(word in normalized for word in ("why", "because", "amber", "green", "red", "recommendation", "blocker")):
        return False
    role_phrases = ("what about", "what does", "what do", "what can", "what are", "how does", "how do", "your role", "your tools", "what tools", "uses", "use an", "tell me about", "explain", "who is")
    meaningful = [word for word in re.findall(r"[a-z]+", normalized) if word not in STOP_WORDS]
    return "agent" in normalized or any(phrase in normalized for phrase in role_phrases) or len(meaningful) <= 2

def _is_capability_question(question: str) -> bool:
    lowered = question.lower()
    return any(phrase in lowered for phrase in (
        "how do", "how does", "how can", "normally", "how it works", "how you work",
        "what tools", "which tools", "do you use", "use an ocr", "use ocr", "process",
        "workflow", "what can you do", "what do you do", "your role",
    ))

def _agent_capability_answer(agent_id: str, transaction: dict, artifact: dict) -> str:
    detail = AGENT_DETAILS[agent_id]
    return (
        f"{detail['name']} — How It Works\n\n"
        f"Chronological process: {AGENT_METHODS[agent_id]}\n\n"
        f"Tools used: {', '.join(detail['tools'])}.\n\n"
        f"Can answer: {detail['can']}\n\n"
        f"Boundary: {AGENT_SCOPE[agent_id]}"
    )

def _case_data_answer(question: str, transaction: dict) -> str | None:
    lowered = question.lower()
    agreement = _document(transaction, "Purchase Agreement")
    amendment = _document(transaction, "Amendment #1")
    if any(term in lowered for term in ("price", "purchase price", "cost", "offer amount")):
        quote, source = _sentence(agreement, ["purchase price"])
        counter = next((item for item in transaction["documents"] if item["name"] == "Counteroffer"), None)
        if counter:
            counter_quote, counter_source = _sentence(counter, ["purchase price"])
            return f"Price information in the retained records:\n• “{quote}” — {source}\n• “{counter_quote}” — {counter_source}\n\nThese amounts conflict until a signed superseding record resolves them."
        return f"Price information in the retained agreement:\n• “{quote}” — {source}"
    if any(term in lowered for term in ("deposit", "earnest money", "earnest-money")):
        receipt = _document(transaction, "Deposit Receipt")
        quote, source = _sentence(receipt, ["receipt", "requested deposit", "pending confirmation", "confirmed by escrow"])
        return f"Deposit information:\n• “{quote}” — {source}"
    if any(term in lowered for term in ("closing date", "close date", "when does", "timeline", "deadline")):
        quote, source = _sentence(amendment, ["controlling closing date", "closing date"])
        return f"Closing-date information:\n• “{quote}” — {source}"
    if any(term in lowered for term in ("buyer", "seller", "party", "parties", "agent name")):
        quote, source = _sentence(agreement, ["buyer", "seller"])
        return f"Party information:\n• “{quote}” — {source}"
    if any(term in lowered for term in ("property", "address", "apn", "parcel")):
        quote, source = _sentence(agreement, ["apn", "property"])
        return f"Property information:\n• “{quote}” — {source}"
    if any(term in lowered for term in ("what documents", "which documents", "document list", "records are")):
        names = ", ".join(item["name"] for item in transaction["documents"])
        return f"This case contains {len(transaction['documents'])} retained records:\n{names}\n\nAsk for a document name to see what it says and where it is cited."
    return None

def _signature_answer(transaction: dict) -> str:
    names = ("Purchase Agreement", "Amendment #1", "Counteroffer", "Agency Disclosure", "Inspection Contingency Removal", "Possession and Repair Confirmation")
    lines = []
    for name in names:
        document = next((item for item in transaction["documents"] if item["name"] == name), None)
        if not document: continue
        if "seller signature missing" in document["text"].lower():
            status = "seller signature is missing"
        elif "NOT RETURNED" in document["text"] and name == "Counteroffer":
            status = "buyer acceptance was not returned"
        elif "/s/" in document["text"]:
            status = "simulated execution/receipt is recorded"
        else:
            status = "no execution entry was found"
        lines.append(f"• {name}: {status} ({citation(document, 'signature')})")
    return "Signature-related records in this demo packet:\n" + "\n".join(lines)

def answer_follow_up(question: str, agent_id: str, transaction: dict, artifact: dict, direct: bool = False) -> str:
    """Answer from retained records first, then safe general education when needed."""
    lowered = question.lower()
    normalized = re.sub(r"\bwt\b", "what", lowered)
    normalized = re.sub(r"\babt\b", "about", normalized)
    normalized = re.sub(r"\bu\b", "you", normalized)
    scope = AGENT_SCOPE.get(agent_id, "I will answer from the retained transaction records.")
    mentioned = _mentioned_agent(question)
    role_question = any(phrase in normalized for phrase in ("what about", "what do you do", "what can you do", "what are your", "your role", "your tools", "explain your", "tell me about", "what did you do"))
    if mentioned and is_agent_overview_question(normalized):
        return _agent_overview(mentioned, transaction, artifact if mentioned == agent_id else {}, direct and mentioned == agent_id)
    if role_question and agent_id == "orchestrator":
        return (
            "Light's Overview\n\n"
            "Light is the Doorlight Orchestrator. It keeps the case conversation clear, chooses whether a full review is needed, and combines specialist results without pretending to be one of the specialists.\n\n"
            "It can explain the transaction, answer questions from the retained packet, explain any agent's job and tools, and run the seven-stage review when asked.\n\n"
            "For a specific role, ask for the Evidence Agent, Compliance Agent, or another named agent. Light will explain that role in plain English; it will only use direct specialist mode when you select that specialist in the sidebar."
        )
    if direct and "what did you do" in normalized:
        return _agent_overview(agent_id, transaction, artifact, True)
    if direct and _is_capability_question(normalized):
        return _agent_capability_answer(agent_id, transaction, artifact)
    if role_question and (direct or any(word in normalized for word in ("compliance", "evidence", "policy", "document", "reconcil", "risk", "intake"))):
        return _agent_overview(agent_id, transaction, artifact, direct)
    if any(term in lowered for term in ("signature", "signatures", "signed", "execute")):
        return f"{scope}\n\n{_signature_answer(transaction)}\n\nThe source record, rather than this summary, controls whether an execution is complete."
    data_answer = _case_data_answer(question, transaction)
    if data_answer:
        return f"{scope}\n\n{data_answer}"
    if agent_id == "risk-agent" and any(term in lowered for term in ("why", "red", "amber", "green", "recommendation", "risk")):
        lane = artifact.get("lane", "current")
        findings = artifact.get("findings", [])[:3]
        evidence = artifact.get("evidence", [])[:3]
        reason = "\n".join(f"• {finding}" for finding in findings) or "• The retained evidence requires further review."
        sources = "; ".join(evidence) or "the retained packet"
        return f"{scope}\n\nThe current recommendation is {lane}. It is based on:\n{reason}\n\nSources: {sources}\n\nNext step: {artifact.get('nextAction', 'Complete the documented follow-up and request a new review.')}"
    for keyword, explanation in GENERAL.items():
        if keyword in lowered:
            docs = _relevant_documents(question, transaction, 2)
            citations = []
            for document in docs:
                quote, source = _sentence(document, [keyword])
                citations.append(f"• “{quote}” — {source}")
            source_section = "\n".join(citations) if citations else "• No retained case page directly addresses that general concept."
            return f"{scope}\n\n{explanation}\n\nRelated source material:\n{source_section}\n\nThis is general educational information, not legal, tax, lending, insurance, or title advice."
    documents = _relevant_documents(question, transaction)
    if documents:
        terms = [token for token in re.findall(r"[a-z]{3,}", lowered) if token not in STOP_WORDS]
        evidence = []
        for document in documents:
            quote, source = _sentence(document, terms)
            evidence.append(f"• “{quote}” — {source}")
        return f"{scope}\n\nHere is what the retained case record supports:\n" + "\n".join(evidence) + "\n\nIf your question depends on a fact not in these pages, the appropriate professional should confirm it."
    return f"{scope}\n\nI do not have a retained source that answers that question for this case. Ask for the relevant document, party, amount, date, or condition and I will search the packet; for a real transaction, confirm legal, lending, title, tax, and insurance questions with the appropriate professional."
