"""Audited non-agent services represented in the Draw.io Stage 8 workflow.

These are local-demo services, not closing, payment, email, e-sign, title, or lender
integrations. The orchestrator may create only an internal task or message draft.
"""
from __future__ import annotations
from .agents.base import citation

def commission_calculation(transaction: dict) -> dict:
    terms = transaction["commission"]; price = transaction["purchasePrice"]
    gross = round(price * terms["sidePercent"] / 100, 2)
    broker = round(gross * terms["brokerSplitPercent"] / 100, 2)
    agent = round(gross * terms["agentSplitPercent"] / 100, 2)
    agreement = next((d for d in transaction["documents"] if d["name"] == "Commission Agreement"), None)
    return {"summary": f"Advisory buyer-side commission calculation: ${gross:,.2f} gross; ${broker:,.2f} broker split; ${agent:,.2f} agent split before fees.",
            "inputs": {"salePrice": price, "sidePercent": terms["sidePercent"], "brokerSplitPercent": terms["brokerSplitPercent"], "agentSplitPercent": terms["agentSplitPercent"], "fees": terms["fees"]},
            "evidence": [citation(agreement)] if agreement else ["Configured demo commission terms; agreement source unavailable."], "status": "ADVISORY_ONLY"}

def closing_control(transaction: dict, risk: dict) -> dict:
    lane = risk["lane"]
    if lane == "GREEN":
        return {"status": "LOCAL_READINESS_TASK_ALLOWED", "summary": "All retained checks reached the Green route; created an internal readiness-review task only. No funds, recording, or closing execution occurs.", "action": "Create internal readiness review task"}
    if lane == "AMBER":
        return {"status": "HUMAN_REVIEW_REQUIRED", "summary": "An administrative confirmation remains open; final package freeze and closing authorization are held for human review.", "action": "Assign transaction coordinator review"}
    return {"status": "BROKER_OR_EXPERT_REVIEW_REQUIRED", "summary": "A material exception blocks the final package; record freeze, closing authorization, and external execution remain unavailable.", "action": "Escalate internal review to broker or appropriate expert"}

def communication_draft(transaction: dict, risk: dict) -> dict:
    lane = risk["lane"]; recipient = "Transaction Coordinator" if lane != "RED" else "Broker"
    return {"status": "DRAFT_ONLY", "recipient": recipient, "summary": f"Prepared an internal {recipient.lower()} draft for the {lane} route. External sending remains disabled in this local MVP.", "allowed": transaction["communication"]["allowedActions"]}
