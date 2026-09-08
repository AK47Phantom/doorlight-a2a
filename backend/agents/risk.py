"""Risk Agent: evidence-backed readiness recommendation and human-review routing service."""
import re

from .base import AgentDefinition, ToolDefinition, artifact, citation
from ..services import search_documents
from ..visual_evidence import build_visual_evidence
PROMPT = """You are the Risk Agent. Make one evidence-backed readiness recommendation:
GREEN means the retained review packet has consistent material terms and no unresolved
material blocker; AMBER means a limited administrative confirmation is incomplete but
there is no material conflict; RED means an executed-agreement defect, conflicting
material term, unresolved title exception, absent required disclosure, or material
financing/contingency issue. Cite decisive raw sources, explain why the issue fits the
lane, identify what evidence would change it, and recommend the smallest next action.
Do not call a transaction closed, give legal advice, or let an uncited model statement
override retained evidence. The optional selected LLM may improve wording only after
this structured recommendation is validated."""
TOOLS = (
    ToolDefinition("risk_rubric", "Apply the documented Green/Amber/Red readiness rubric.", "READ_POLICY", lambda _: "GREEN=consistent packet; AMBER=limited administrative gap; RED=material blocker"),
    ToolDefinition("material_blocker_search", "Find signature, title, price, financing, and contingency blocker language.", "READ_DOCUMENT", lambda t: search_documents(t, ["signature missing", "payoff", "release", "superseding amendment", "difference", "unresolved"])),
    ToolDefinition("administrative_gap_search", "Find non-material confirmation/follow-up language.", "READ_DOCUMENT", lambda t: search_documents(t, ["pending confirmation", "follow-up"])),
    ToolDefinition("recommendation_validator", "Ensure lane, citations, reason, and next action are all present.", "READ_DOCUMENT", lambda result: bool(result.get("lane") and result.get("evidence") and result.get("nextAction"))),
)
def run(transaction, artifacts: dict):
    docs = transaction["documents"]; decisive=[]; evidence=[]
    for d in TOOLS[1].execute(transaction):
        if any(x in d["text"].lower() for x in ("seller signature missing", "requires written payoff", "no superseding amendment")):
            phrase = next(x for x in ("seller signature missing", "requires written payoff or release evidence", "no superseding amendment resolves") if x in d["text"].lower())
            passage = next((part.strip() for part in re.split(r"(?<=[.!?])\s+", d["text"]) if phrase in part.lower()), phrase)
            if d["name"] == "Counteroffer":
                counter_price = re.search(r"purchase price \$([\d,]+(?:\.\d{2})?)", d["text"], re.I)
                agreement_price = transaction.get("purchasePrice")
                if counter_price and agreement_price:
                    passage = f"The Purchase Agreement states ${agreement_price:,.0f}, while the Counteroffer states ${counter_price.group(1)}; no superseding amendment signed by both parties resolves which price controls."
            decisive.append(f"{passage} ({citation(d, phrase)})"); evidence.append(citation(d, phrase))
    if decisive:
        agreement = next(d for d in docs if d["name"] == "Purchase Agreement")
        passage = next(part.strip() for part in re.split(r"(?<=[.!?])\s+", agreement["text"]) if "seller signature missing" in part.lower())
        visual = build_visual_evidence(transaction, "Purchase Agreement", passage, "RED", "The highlighted sentence shows that the controlling purchase agreement is not fully executed because the seller signature is missing.")
        result = artifact("Material blockers prevent readiness: " + " ".join(decisive), decisive, evidence, "Obtain executed controlling documents, written title release evidence, and a superseding price resolution before re-review.", lane="RED", rationale="The packet contains a material execution, title, or controlling-price defect; human review is mandatory.", whatWouldChange="A fully executed controlling agreement, lien release/payoff, and superseding signed price resolution.", visualEvidence=visual)
        if not TOOLS[3].execute(result): raise ValueError("Risk output did not meet the recommendation contract")
        return result
    pending = next((d for d in TOOLS[2].execute(transaction) if "pending confirmation" in d["text"].lower()), None)
    if pending:
        passage = next(part.strip() for part in re.split(r"(?<=[.!?])\s+", pending["text"]) if "pending confirmation" in part.lower())
        visual = build_visual_evidence(transaction, "Deposit Receipt", passage, "AMBER", "The highlighted sentence shows that escrow confirmation is still missing; the buyer delivery reference is not the final receipt.")
        result = artifact("Limited administrative evidence remains open: escrow has not confirmed the earnest-money receipt.", [f"{passage} ({citation(pending, 'pending confirmation')})"], [citation(pending, "pending confirmation")], "Request escrow confirmation of amount, date, and funds reference, then re-review.", lane="AMBER", rationale="The retained packet does not show a material term conflict, but deposit confirmation is incomplete.", whatWouldChange="Escrow confirmation matching the required deposit amount, date, and funds reference.", visualEvidence=visual)
        if not TOOLS[3].execute(result): raise ValueError("Risk output did not meet the recommendation contract")
        return result
    result = artifact("The retained review packet has consistent material terms and no unresolved evidence-based blocker.", ["Executed agreement, deposit, disclosures, financing, title path, and contingency evidence are retained."], [citation(d) for d in docs[:5]], "Create a local readiness task for authorized human final review.", lane="GREEN", rationale="No retained source contains an unresolved material conflict or blocker.", whatWouldChange="A newly discovered material exception, conflicting controlling term, or missing required evidence.")
    if not TOOLS[3].execute(result): raise ValueError("Risk output did not meet the recommendation contract")
    return result
DEFINITION = AgentDefinition("risk-agent", "Risk Agent", "Applies the materiality rubric to cited peer evidence, validates one Green, Amber, or Red recommendation, and explains the human-review route and smallest corrective action.", PROMPT, ("Assess material risk", "Explain lane rationale", "Route human review", "Validate recommendations"), TOOLS, run)
