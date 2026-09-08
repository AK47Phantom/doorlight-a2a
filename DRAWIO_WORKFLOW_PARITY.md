# Draw.io workflow parity

This document maps `ai doorlight design (1).json` to the local Doorlight MVP. The diagram is the workflow reference; the code deliberately keeps production-only integrations at an explicit local-demo boundary rather than pretending that a synthetic demo can send money, email, e-sign envelopes, or title instructions.

## End-to-end flow

1. **Entry, conversation, and normalization.** Light accepts a user request and selected transaction. `backend/app.py` classifies the request, attaches transaction, session, actor, source, event type, and timestamp, and records an `Input & Event Normalization` audit event.
2. **Context manager and planner.** The Orchestrator loads the active case, request, scoped retained documents, and previous workflow context. It records a `Conversation Context & Planner` event, chooses a direct specialist for an agent-specific question or sequences the whole pipeline.
3. **A2A-only handoffs.** The Orchestrator discovers each Agent Card and sends each peer a local JSON-RPC A2A task. Specialists never import or call another specialist. Each endpoint has an independent `AgentExecutor`, `DefaultRequestHandler`, and `InMemoryTaskStore`.
4. **Specialist pipeline.** The seven boxes in the diagram run in order: Transaction Intake → Policy → Document Intake → Evidence → Reconciliation → Compliance → Risk.
5. **Risk, permissions, and outcomes.** The Risk Agent emits the evidence-backed Green/Amber/Red recommendation. The Zone 3 permission check then routes Green to an internal readiness task, Amber to a transaction-coordinator review, and Red to broker/expert review. It cannot execute a closing or an external action.
6. **Stage 8 controlled services.** The orchestrator runs the diagram's commission calculator, closing control, and communication draft as audited local services. They are intentionally services rather than additional peer agents, preserving the core-seven A2A network chosen for this MVP.

## Audit result: every Zone 3 element

The supplied file contains a large **Full Process** page plus focused pages for the assistant, orchestrator, each specialist, human review, and enterprise entry/security zones. The following is the implementation reading of every Zone 3 branch:

| Diagram branch | Behavior in this MVP |
| --- | --- |
| Accepted offer / create case | A selected synthetic accepted-offer case supplies the start event; Intake creates the normalized working record. User-created transactions are a future integration. |
| Document upload / document lifecycle | The retained synthetic packet stands in for uploaded files. Document Intake classifies, hashes, versions, detects duplicate names, associates records to a case, extracts metadata, and runs bounded local vision/OCR preflight. |
| Evidence record | Extracted facts retain fact kind, source citation, page region, extractor/model version, and confidence. The original retained page remains authoritative. |
| Conflict decision | Reconciliation compares the agreement chain and material fields. A clear term is carried forward; an unresolved term becomes a cited exception for Compliance and Risk. |
| Checklist decision branches | Compliance supports `SATISFIED`, `PARTIAL`, `MISSING`, `CONTRADICTORY`, `NOT_APPLICABLE`, and `HUMAN_JUDGMENT_REQUIRED`; each result is evidence-bound. |
| Green / Amber / Red branch | Risk produces the lane from cited artifacts. Green may create a logged local readiness task; Amber goes to coordinator review; Red goes to broker/appropriate expert review. |
| Commission calculation | The post-risk advisory service reads retained commission terms, calculates gross/broker/agent amounts and fees, and flags the output as non-payment, non-accounting advice. |
| Closing controls | The post-risk service checks the route and holds package freeze, authorization, funds, recording, and closing execution behind the local permission boundary. |
| Communication and permissions | The post-risk service creates a recipient-scoped internal draft only. The permission decision and every tool/service use are recorded in SQLite. No notification is externally sent. |
| Conversation manager | Browser-session chat preserves selected case, prior messages, responder changes, run/task IDs, and retained artifacts. Light expands short follow-ups using the active transaction context. |

This means the MVP represents the diagram's **Zone 3 decision and control model end-to-end**, with local, inspectable substitutions for document and action providers. It does not claim to implement the diagram's enterprise perimeter or third-party systems.

## Diagram element map

| Draw.io element | MVP implementation |
| --- | --- |
| AI Assistant / Conversation Manager / sessions, turns, intent | Light UI plus `normalize_input`, `route_follow_up`, run IDs, session IDs, and persisted run records in `backend/app.py` / `backend/store.py`. |
| Orchestrator controls sequence, context, policies, failures, human escalation | `run_workflow` in `backend/app.py`; its run trace visibly records normalization, planning, tool governance, A2A stage results, permissions, and failures. |
| A2A agent communication | `ClientFactory` resolves Agent Cards and communicates with `/agents/{agent-id}` via JSON-RPC. Cards are discoverable at `/.well-known/agent-card.json`. |
| Transaction Intake: create case | `backend/agents/transaction_intake.py`: normalizes parties, property, financing, dates, representation, and missing fields. |
| Policy & Rules: select policy | `backend/agents/policy.py`: selects the supplied California policy/checklist scope and explains its basis. |
| Document Intake: OCR, classifier, versioning, hashing, metadata, association | `backend/agents/document_intake.py` and `backend/services.py`: source-text reader, classifier, version registry, SHA-256 fingerprint, metadata extractor, duplicate detector, transaction associator, and local vision/OCR preflight. |
| Evidence: fact, source, page, region, version, confidence, model | `backend/agents/evidence.py` and `extract_facts`: provenance-bound facts carry citation, synthetic source-page region, confidence, and extractor version; retained source page/version remains authoritative. |
| Reconciliation: agreement chain; parties, property, money, terms, dates, signatures | `backend/agents/reconciliation.py`: agreement-chain builder, term comparator, signature/title searches, and commission-term reader. It distinguishes material conflicts from pending administration. |
| Compliance: checklist, policy search, document search, evidence retrieval | `backend/agents/compliance.py`: applies constrained requirement statuses and records cited evidence/retrieved facts without selecting a risk lane. |
| Risk & escalation | `backend/agents/risk.py` issues the recommendation; selected Gemini/Ollama output may synthesize only when schema-valid and consistent with that artifact. It cannot override decisive evidence with a hard-coded case color. |
| Commission Agent tools | `backend/workflow_services.py::commission_calculation`: agreement citation, purchase price, percentage, split, fees, advisory result. No invoice, accounting, or payment. |
| Closing Agent | `closing_control`: final package/readiness gate, record freeze/authorization hold, and an internal local task only. No closing, recording, escrow, or funds action. |
| Communication Agent | `communication_draft`: an internal recipient and draft-only message. External sending is disabled. |
| Permission controls / execute vs no / human review | SQLite audit events record agent, tool/service, purpose, decision, summary, and timestamp. Green allows only a local readiness task; Amber and Red require review. |
| Explainability record | The persisted A2A artifact and UI trace show result, citations, recommendation, next step, provider synthesis decision, and audit records. |

## External enterprise zones

The diagram also includes browser/mobile/email/e-sign entry points; CRM, MLS, accounting, calendar, title, escrow, lender, insurance, and storage systems; plus CDN/API gateway/WAF, authentication, authorization, encryption, rate limiting, and enterprise monitoring. Those are **not live integrations in this local synthetic MVP**. They are represented by the normalized-input and controlled-action boundaries so they can be connected safely later.

Before production use, add authenticated users and role-based authorization, a secrets manager, encrypted production storage, API gateway/WAF/rate limits, real provider adapters, document retention policy, observability, and approved integrations for every external system. Do not treat the demo's advisory output as legal, brokerage, title, lending, or closing authority.
