"""Policy Agent: selects a bounded policy scope and requirements checklist."""
from .base import AgentDefinition, ToolDefinition, artifact
from ..services import select_policy
PROMPT = """You are the Policy & Rules Agent. Select only from the provided local policy
context after checking jurisdiction, side, transaction type, representation, and
financing. Explain the applicability basis and enumerate the selected checklist.
Do not invent laws, offer legal advice, evaluate whether documents satisfy a rule,
or make a Green/Amber/Red recommendation. Surface any attribute that would change
policy scope and send only the required checklist downstream."""
TOOLS = (
    ToolDefinition("policy_search", "Locate the applicable supplied policy by transaction attributes.", "READ_POLICY", select_policy),
    ToolDefinition("checklist_selector", "Return only requirements for the selected policy version.", "READ_POLICY", lambda t: t["policyContext"]["checklist"]),
)
def run(transaction, _: dict):
    policy = TOOLS[0].execute(transaction); checklist = TOOLS[1].execute(transaction)
    return artifact(f"Selected {policy['id']} v{policy['version']} for this {transaction['jurisdiction']} {transaction['type'].lower()}.", [f"Applicability basis: {', '.join(policy['basis'])}", f"Checklist scope: {len(checklist)} requirements", f"Requirements: {', '.join(checklist)}"], [f"{policy['id']} v{policy['version']}"], "Pass policy scope and checklist to Document and Compliance Agents.", policy=policy)
DEFINITION = AgentDefinition("policy-agent", "Policy & Rules Agent", "Selects the supplied policy version from jurisdiction and transaction attributes, then provides a bounded checklist without evaluating compliance or risk.", PROMPT, ("Select applicable policy", "Explain scope", "Return bounded checklist"), TOOLS, run)
