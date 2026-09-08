"""Reconciliation Agent: controlling-document and material-term comparison service."""
from .base import AgentDefinition, ToolDefinition, artifact, citation
from ..services import compare_material_terms, search_documents
PROMPT = """You are the Reconciliation Agent. Determine which retained agreement,
amendment, and counteroffer records control a material term, then compare parties,
property, signatures, money, dates, title, financing, deposits, and contingencies.
An amendment can supersede only the term it explicitly changes. State both sides of
every unresolved conflict with citations. A pending administrative confirmation is
not a material conflict by itself. Do not assign a risk color or hide uncertainty."""
TOOLS = (
    ToolDefinition("agreement_chain_builder", "Find controlling agreement, amendments, and counteroffers.", "READ_DOCUMENT", lambda t: search_documents(t, ["Purchase Agreement", "Amendment", "Counteroffer"])),
    ToolDefinition("term_comparator", "Compare material terms among controlling candidates.", "READ_DOCUMENT", compare_material_terms),
    ToolDefinition("signature_checker", "Find signature language in retained agreements.", "READ_DOCUMENT", lambda t: search_documents(t, ["signature"])),
    ToolDefinition("title_exception_search", "Find title exceptions and release requirements.", "READ_DOCUMENT", lambda t: search_documents(t, ["Title", "lien", "payoff", "release"])),
    ToolDefinition("commission_term_reader", "Retrieve approved commission terms for money-term reconciliation only.", "READ_DOCUMENT", lambda t: search_documents(t, ["Commission Agreement", "commission", "split", "fee"])),
)
def run(transaction, _: dict):
    docs = transaction["documents"]; findings=[]; evidence=[]
    agreement = next((d for d in docs if d["name"] == "Purchase Agreement"), None)
    amendment = next((d for d in docs if d["name"] == "Amendment #1"), None)
    if agreement: evidence.append(citation(agreement)); findings.append(f"Controlling chain begins with Purchase Agreement {agreement['version']}.")
    if amendment:
        phrase = next((line for line in amendment["text"].splitlines() if "controlling closing date" in line.lower()), "The amendment changes the closing milestone.")
        evidence.append(citation(amendment, "controlling closing date")); findings.append(f"Amendment #1 controls only the closing date: {phrase}")
    counter = next((d for d in docs if d["name"] == "Counteroffer"), None)
    for issue in TOOLS[1].execute(docs):
        findings.append(issue["detail"]); evidence.extend(issue["evidence"])
    if agreement and "seller signature missing" in agreement["text"].lower(): findings.append("Executed agreement exception: seller signature is missing.")
    title = next((d for d in TOOLS[3].execute(transaction) if d["name"] == "Preliminary Title Report"), None)
    if title and "requires written payoff or release evidence" in title["text"].lower():
        finding = next(part.strip() for part in title["text"].split(".") if "requires written payoff or release evidence" in part.lower())
        findings.append(f"Title exception remains unresolved: {finding}."); evidence.append(citation(title, "requires written payoff or release evidence"))
    commission = next((d for d in TOOLS[4].execute(transaction) if d["name"] == "Commission Agreement"), None)
    if commission:
        findings.append("Commission terms were retained as a downstream advisory input and were not used to change the purchase-price agreement chain.")
        evidence.append(citation(commission))
    if not any("conflict" in finding.lower() or "exception" in finding.lower() for finding in findings): findings.append("No unresolved material term conflict identified in the retained agreement chain.")
    return artifact("Reconciled controlling documents and material terms.", findings, list(dict.fromkeys(evidence)), "Pass controlling chain and unresolved exceptions to Compliance Agent.")
DEFINITION = AgentDefinition("reconciliation-agent", "Reconciliation Agent", "Builds the controlling agreement chain and compares material terms, signatures, title exceptions, and conflicts while separating administrative follow-up from true discrepancies.", PROMPT, ("Build controlling chain", "Compare material terms", "Identify exceptions", "Separate operational from material issues"), TOOLS, run)
