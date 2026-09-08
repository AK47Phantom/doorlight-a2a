# Doorlight A2A — Python Agent MVP

Doorlight is a local, synthetic real-estate transaction workflow demonstration. The React/Vite interface is the presentation layer; a Python/FastAPI service hosts seven official A2A agents and the controlled tool-access/audit layer.

## Start it

```bash
npm install
uv sync
cp .env.example .env
npm run dev
```

The UI is at `http://127.0.0.1:5173`; its Python API is at `http://127.0.0.1:3001`. Python packages are declared in `pyproject.toml`. If `uv` is not installed, install it from <https://docs.astral.sh/uv/>. The `.env` file is local and ignored by Git; add only the provider settings you plan to use.

```bash
npm run build
npm run test:api
```

## How it works

Light sends a request to the Doorlight orchestration API. The orchestrator discovers each local Agent Card and sends an A2A JSON-RPC task to each specialist. Agents do not call one another. SQLite retains run history, artifacts, follow-ups, and audit events across browser refreshes and restarts.

For an element-by-element mapping to the supplied workflow diagram, including the explicit local-demo boundary for external systems, see [DRAWIO_WORKFLOW_PARITY.md](DRAWIO_WORKFLOW_PARITY.md).

| Stage | Agent | Unique tools / output |
| --- | --- | --- |
| 1 | Transaction Intake | Case lookup, party normalization, milestone reader → normalized case and unknown fields |
| 2 | Policy & Rules | Policy search, checklist selector → policy basis and bounded requirement scope |
| 3 | Document Intake | Text adapter, classifier, version registry, fingerprint, metadata → custody-ready inventory |
| 4 | Evidence | Document search, fact extraction, citation builder → source-grounded facts and gaps |
| 5 | Reconciliation | Agreement-chain builder, term comparator, signature/title search → controlling terms and conflicts |
| 6 | Compliance | Checklist, policy/document search, per-requirement evaluator → constrained status with citations |
| 7 | Risk | Materiality rubric, blocker/admin-gap search, validator → Green, Amber, or Red recommendation |

Agent Cards are at `/agents/{agent-id}/.well-known/agent-card.json`; JSON-RPC endpoints are `/agents/{agent-id}`. Every agent has its own official `AgentExecutor`, `DefaultRequestHandler`, and `InMemoryTaskStore`.

## Zone 3: controlled tool access

Every tool read is logged with agent, run, purpose, decision, and timestamp. This MVP creates only local Doorlight tasks, reminders, and message drafts; it never sends email or changes an external transaction system.

The tools are real local service adapters in `backend/services.py`: they inspect, classify, compare, fingerprint, and evaluate the retained synthetic packet. Document Intake also renders a cover-page contact sheet and sends it once per packet version to the local `qwen2.5vl:7b` vision model for a bounded visual/OCR preflight. The vision result is cached in `backend/.cache/`, displayed as a derived observation, and never replaces retained source text/page citations as the authoritative evidence. This is an intake preview, not full-document OCR. These are intentionally replaceable boundaries for real OCR, policy, document-management, or transaction-system integrations later.

- Green can create a local readiness task/draft.
- Amber and Red require human review.
- Legal ambiguity, conflicting evidence, high-risk compliance, unusual contracts, and material financial discrepancies require review.

Records in `backend/domain.py` are synthetic fixtures, not legal advice or customer data. Dense source bodies and transaction-specific simulated signatures are authored in `backend/document_content.py`; shared pagination is in `backend/document_pages.py`. Regenerate the matching page images and multipage PDFs with `uv run python scripts/generate_demo_documents.py`. Research boundaries and document-anatomy influences are in [docs/document-research.md](docs/document-research.md).

Generated folders such as `node_modules/`, `.venv/`, `dist/`, Python caches, the SQLite runtime database, and vision/OCR cache are intentionally excluded from source control. They are recreated by the setup and run commands above.

## Providers

The UI retains Gemini and Ollama selection and health reporting. Set `GEMINI_API_KEY`/`GEMINI_API_KEYS` for Gemini, or run Ollama at `OLLAMA_HOST` (default `http://127.0.0.1:11434`). The selected provider receives a short, validated Risk artifact for synthesis after evidence tools finish; output and request time are bounded so a slow local model cannot make the completed workflow appear frozen. Malformed, quota-limited, unavailable, or evidence-contradicting output is rejected and the validated specialist artifact remains. `qwen2.5vl:7b` handles the bounded image preflight; `llama3.1:8b` remains the text model. Preserved page text is authoritative in this MVP.

## Private GitHub sharing

This repository is prepared for a private GitHub upload. Local API keys, SQLite state, model/OCR caches, dependencies, and build output are excluded by `.gitignore`; your friend supplies their own `.env` and local models. Follow the beginner walkthrough in [docs/github-sharing.md](docs/github-sharing.md).

## Project map

- `backend/app.py` — API, orchestration, persistence, and permission boundary.
- `backend/a2a_runtime.py` — official A2A server wiring and Agent Cards.
- `backend/agents/` — one inspectable module per specialist: prompt, tools, and artifact behavior.
- `backend/domain.py` — synthetic transactions.
- `backend/document_content.py` — original fictional instruments and execution states.
- `backend/document_pages.py` — non-truncating source pagination and page lookup.
- `backend/store.py` — SQLite retention.
- `scripts/generate_demo_documents.py` — varied PNG/PDF layouts generated from the same source bodies.
- `src/` — React/Vite interface.
