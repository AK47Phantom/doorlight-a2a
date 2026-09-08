"""Shared contracts for independently declared Doorlight A2A specialists.

An agent is not a display label: it owns an operating prompt, a limited tool belt,
an input boundary, and a schema-checked output artifact.  The simple local tools
operate only on the synthetic transaction packet; adapters can later replace them
with real document, policy, or transaction-system integrations.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

Artifact = dict[str, Any]

@dataclass(frozen=True)
class ToolDefinition:
    """A governed, inspectable tool exposed to exactly the specialists that need it."""
    name: str
    purpose: str
    access: str
    execute: Callable[..., Any]

@dataclass(frozen=True)
class AgentDefinition:
    id: str
    name: str
    description: str
    prompt: str
    skills: tuple[str, ...]
    tools: tuple[ToolDefinition, ...]
    run: Callable[[dict[str, Any], dict[str, Artifact]], Artifact]

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(tool.name for tool in self.tools)

def citation(document: dict[str, Any], phrase: str | None = None) -> str:
    page = document.get("page", 1)
    if phrase:
        from ..document_pages import page_for_phrase
        page = page_for_phrase(document, phrase)
    return f"{document['name']} {document['version']}, page {page}"

def docs_with(transaction: dict, *terms: str) -> list[dict]:
    return [d for d in transaction["documents"] if any(term.lower() in (d["name"] + " " + d["text"]).lower() for term in terms) or not terms]

def artifact(summary: str, findings: list[str], evidence: list[str], next_action: str, **extra: Any) -> Artifact:
    """Return the common UI/A2A artifact shape and reject silent bad output."""
    if not all(isinstance(value, str) and value.strip() for value in (summary, next_action)):
        raise ValueError("Agent artifact requires a non-empty summary and next action.")
    if not all(isinstance(value, str) for value in findings + evidence):
        raise ValueError("Agent artifact findings and evidence must be readable strings.")
    return {"summary": summary, "findings": findings, "evidence": evidence, "nextAction": next_action, **extra}
