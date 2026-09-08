from .transaction_intake import DEFINITION as intake
from .policy import DEFINITION as policy
from .document_intake import DEFINITION as document
from .evidence import DEFINITION as evidence
from .reconciliation import DEFINITION as reconciliation
from .compliance import DEFINITION as compliance
from .risk import DEFINITION as risk

AGENTS = (intake, policy, document, evidence, reconciliation, compliance, risk)
BY_ID = {agent.id: agent for agent in AGENTS}
