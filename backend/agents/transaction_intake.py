"""Transaction Intake Agent: creates a normalized, source-bounded case foundation."""
from .base import AgentDefinition, ToolDefinition, artifact
from ..services import transaction_snapshot

PROMPT = """You are the Transaction Intake Agent. Build a clean case foundation from
authorized transaction data only. Verify case identity, property, representation,
parties, financing, jurisdiction, milestones, and source availability. Clearly label
unknown or absent facts. Do not infer legal status, make a risk recommendation, or
silently repair conflicting records. Your output will be consumed by Policy and
Document agents, so preserve factual provenance and distinguish source data from
operational assumptions."""
TOOLS = (
    ToolDefinition("transaction_lookup", "Read the selected synthetic transaction record.", "READ_TRANSACTION", transaction_snapshot),
    ToolDefinition("party_normalizer", "Normalize the supplied buyer, seller, agent, and escrow roles.", "READ_TRANSACTION", lambda t: t["parties"]),
    ToolDefinition("milestone_reader", "Read accepted-offer, deposit, contingency, and closing milestones.", "READ_TRANSACTION", lambda t: t["importantDates"]),
)
def run(transaction, _: dict):
    snapshot = TOOLS[0].execute(transaction); parties = TOOLS[1].execute(transaction); dates = TOOLS[2].execute(transaction)
    unknown = [field for field in ("buyer", "seller", "buyerAgent", "listingAgent", "escrowOfficer") if not parties.get(field)]
    findings = [f"Case ID: {snapshot['id']}; property: {snapshot['property']}", f"Parties: Buyer {parties['buyer']}; Seller {parties['seller']}; Buyer Agent {parties['buyerAgent']}", f"Transaction: {snapshot['side']}-side {snapshot['type']}; {snapshot['financing']} financing; {snapshot['jurisdiction']}", f"Milestones retained: {', '.join(f'{key} {value}' for key, value in dates.items())}"]
    if unknown: findings.append(f"Unknown intake fields: {', '.join(unknown)}")
    return artifact(f"Normalized transaction {snapshot['id']} for {snapshot['property']}.", findings, ["Transaction Cover Sheet · synthetic case context"], "Pass the normalized case foundation to Policy Agent.", normalizedCase=snapshot, unknownFields=unknown)
DEFINITION = AgentDefinition("transaction-intake-agent", "Transaction Intake Agent", "Builds a source-bounded case foundation by normalizing parties, property, representation, financing, and milestone dates while explicitly flagging unknown intake fields.", PROMPT, ("Normalize transaction intake", "Identify absent source fields", "Preserve case provenance"), TOOLS, run)
