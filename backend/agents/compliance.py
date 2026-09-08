"""Compliance Agent: requirement-by-requirement checklist evaluation service."""
from .base import AgentDefinition, ToolDefinition, artifact
from ..services import extract_facts, requirement_status, search_documents, select_policy
PROMPT = """You are the Compliance Agent. Apply only the supplied checklist version.
For every requirement, return one status: SATISFIED, PARTIAL, MISSING,
CONTRADICTORY, NOT_APPLICABLE, or HUMAN_JUDGMENT_REQUIRED; include the smallest
evidence-backed explanation and citations. A requirement result is not a legal
conclusion and you must not choose a risk lane. Do not report a requirement as
satisfied merely because a similarly named document exists."""
TOOLS = (
    ToolDefinition("checklist_tool", "Read the selected policy's requirement list.", "READ_POLICY", lambda t: t["policyContext"]["checklist"]),
    ToolDefinition("policy_search", "Confirm policy version and applicability basis.", "READ_POLICY", select_policy),
    ToolDefinition("document_search", "Locate documents relevant to a requirement.", "READ_DOCUMENT", search_documents),
    ToolDefinition("evidence_retrieval", "Retrieve provenance-bound extracted facts before evaluating a requirement.", "READ_DOCUMENT", lambda t, requirement: [fact for document in search_documents(t, requirement.split()) for fact in extract_facts(document)]),
    ToolDefinition("requirement_evaluator", "Evaluate one supplied requirement against evidence.", "READ_DOCUMENT", requirement_status),
)
def run(transaction, artifacts: dict):
    policy = TOOLS[1].execute(transaction); rules=[]; sources=[]; evaluations=[]
    for requirement in TOOLS[0].execute(transaction):
        retrieved = TOOLS[3].execute(transaction, requirement)
        status, evidence = TOOLS[4].execute(transaction, requirement); rules.append(f"{requirement}: {status}"); sources.extend(evidence); evaluations.append({"requirement": requirement, "status": status, "evidence": evidence, "retrievedFacts": retrieved})
    return artifact("Evaluated the applicable checklist against retained evidence.", rules, list(dict.fromkeys(sources)), "Pass requirement statuses and citations to Risk Agent.", policy=policy, evaluations=evaluations)
DEFINITION = AgentDefinition("compliance-agent", "Compliance Agent", "Evaluates each supplied checklist requirement using constrained statuses and source citations, surfacing missing evidence or human judgment without selecting a risk lane.", PROMPT, ("Evaluate checklist", "Return per-requirement statuses", "Cite evidence", "Surface human judgment"), TOOLS, run)
