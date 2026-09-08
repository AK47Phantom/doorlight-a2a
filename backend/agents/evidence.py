"""Evidence Agent: source retrieval and citation-only material fact service."""
from .base import AgentDefinition, ToolDefinition, artifact, citation
from ..services import extract_facts, search_documents
PROMPT = """You are the Evidence Agent. Answer only with claims supported by retained
source language. Search the packet for the user/stage question, extract material
facts and explicit gap language, and attach document/version/page provenance to every
claim. Separate confirmed fact, absent record, incomplete record, and conflicting
record. Never convert evidence into a compliance status or risk lane; when asked why
a transaction is not ready, quote/paraphrase the direct blocker language first."""
TOOLS = (
    ToolDefinition("document_search", "Search retained document names and extracted text.", "READ_DOCUMENT", search_documents),
    ToolDefinition("evidence_retrieval", "Extract material facts and exception language from a source.", "READ_DOCUMENT", extract_facts),
    ToolDefinition("citation_builder", "Format document/version/page provenance.", "READ_DOCUMENT", citation),
)
def run(transaction, _: dict):
    findings, evidence, extracted = [], [], []
    terms = ["pending", "missing", "unresolved", "requires", "difference", "exception", "signature", "price"]
    for d in TOOLS[0].execute(transaction, terms):
        facts = TOOLS[1].execute(d); extracted.extend(facts)
        for item in (item for item in facts if item["kind"] == "exception_language"):
            findings.append(f"{item['citation']}: “{item['value']}”")
            evidence.append(item["citation"])
    if not findings:
        findings.append("No retained document states a pending, missing, unresolved, or conflicting material term.")
        evidence = [citation(d) for d in transaction["documents"][:3]]
    return artifact("Extracted material facts and gaps with document, version, and page provenance.", findings, evidence, "Pass citations and extracted facts to Reconciliation Agent.", facts=extracted)
DEFINITION = AgentDefinition("evidence-agent", "Evidence Agent", "Searches retained sources for material facts and exception language, returning only document/version/page-cited evidence without making compliance or risk conclusions.", PROMPT, ("Search source records", "Extract material facts", "Build citations", "Separate gaps from conclusions"), TOOLS, run)
