"""Official A2A server wiring. Each definition becomes its own discoverable service."""
from __future__ import annotations
import json, inspect
from a2a.helpers import new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, AgentCapabilities, AgentInterface, AgentSkill, Role
from a2a.utils.constants import TransportProtocol
from .agents.base import AgentDefinition

class SpecialistExecutor(AgentExecutor):
    """A small A2A adapter around one specialist's own prompt/tool/artifact contract."""
    def __init__(self, definition: AgentDefinition) -> None: self.definition = definition
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        try:
            payload = json.loads(context.get_user_input())
            answer = self.definition.run(payload["transaction"], payload.get("artifacts", {}))
            if inspect.isawaitable(answer): answer = await answer
            await event_queue.enqueue_event(new_text_message(json.dumps(answer), context_id=context.context_id, task_id=context.task_id))
        except Exception as exc:
            await event_queue.enqueue_event(new_text_message(json.dumps({"error": str(exc)}), context_id=context.context_id, task_id=context.task_id))
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return None

def build_card(definition: AgentDefinition, public_url: str) -> AgentCard:
    path = f"/agents/{definition.id}"
    return AgentCard(
        name=definition.name, description=definition.description, version="1.0.0",
        supported_interfaces=[AgentInterface(url=f"{public_url}{path}", protocol_binding=TransportProtocol.JSONRPC)],
        capabilities=AgentCapabilities(streaming=False), default_input_modes=["text/plain"], default_output_modes=["text/plain"],
        skills=[AgentSkill(id=definition.id, name=definition.name, description=definition.description, tags=list(definition.skills), examples=[f"Run {definition.name} for a transaction"], input_modes=["text/plain"], output_modes=["text/plain"])],
    )

def a2a_routes(definition: AgentDefinition, public_url: str):
    path = f"/agents/{definition.id}"
    card = build_card(definition, public_url)
    handler = DefaultRequestHandler(SpecialistExecutor(definition), InMemoryTaskStore(), card)
    return create_agent_card_routes(card, card_url=f"{path}/.well-known/agent-card.json") + create_jsonrpc_routes(handler, rpc_url=path)
