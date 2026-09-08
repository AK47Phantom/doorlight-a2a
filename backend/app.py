"""Doorlight's one-host Python API, A2A services, workflow orchestration, and audit boundary."""
from __future__ import annotations
import asyncio, json, os, re, socket, uuid
from datetime import datetime, timezone
from pathlib import Path
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from a2a.client import ClientFactory
from a2a.client.client import ClientConfig
from a2a.helpers import get_message_text, new_text_message
from a2a.types import Role, SendMessageRequest
from .a2a_runtime import a2a_routes
from .agents import AGENTS, BY_ID
from .domain import get_transaction, list_cases
from .context_overview import build_context_overview
from .store import DoorlightStore
from .providers import risk_recommendation
from .config import load_local_env, ollama_hosts
from .workflow_services import commission_calculation, closing_control, communication_draft
from .followups import answer_follow_up, is_agent_overview_question
from .agents.base import citation
from .visual_evidence import CACHE_ROOT

load_local_env()

PORT = int(os.getenv("PORT", "3001")); PUBLIC_URL = os.getenv("A2A_PUBLIC_URL", f"http://127.0.0.1:{PORT}")
store = DoorlightStore(os.getenv("DOORLIGHT_DB", "backend/doorlight.db"))
app = FastAPI(title="Doorlight Python A2A Backend")
for definition in AGENTS: app.router.routes.extend(a2a_routes(definition, PUBLIC_URL))

class RunRequest(BaseModel):
    request: str; caseId: str = "48291"; sessionId: str | None = None; provider: str = "OLLAMA"; targetAgent: str | None = None

def now() -> str: return datetime.now(timezone.utc).isoformat()
def event(run: dict, phase: str, title: str, detail: str, state: str="complete", **extra: object) -> None:
    run["events"].append({"id": str(uuid.uuid4()), "at": now(), "phase": phase, "title": title, "detail": detail, "state": state, **extra})
def save(run: dict) -> None: store.save_run(run)

def normalize_input(request: str, case_id: str, session_id: str) -> dict:
    """Diagram-aligned local entry normalization for an AI user request."""
    lowered = request.lower()
    if any(word in lowered for word in ("commission", "split", "fee")): intent = "COMMISSION_CALCULATION"
    elif any(word in lowered for word in ("upload", "document", "ocr")): intent = "DOCUMENT_INGESTION"
    elif any(word in lowered for word in ("reconcile", "amendment", "conflict")): intent = "DOCUMENT_RECONCILIATION"
    elif any(word in lowered for word in ("compliance", "checklist", "requirement")): intent = "COMPLIANCE_EVALUATION"
    elif any(word in lowered for word in ("risk", "amber", "green", "red", "why")): intent = "RISK_EXPLANATION"
    elif any(word in lowered for word in ("sign", "signature", "esign")): intent = "ESIGN_PREPARATION"
    else: intent = "TRANSACTION_STATUS"
    return {"source": "AI_USER_REQUEST", "transactionId": case_id, "actor": "Local demo session", "sessionId": session_id, "eventType": intent, "timestamp": now(), "standardized": True}

async def invoke_agent(agent_id: str, transaction: dict, artifacts: dict) -> dict:
    """Discover the peer's card and send a real local A2A JSON-RPC request."""
    # Vision/OCR is a legitimate longer-running peer operation, so use a bounded
    # explicit A2A client timeout rather than httpx's short default timeout.
    async with httpx.AsyncClient(timeout=float(os.getenv("A2A_AGENT_TIMEOUT_SECONDS", "40"))) as http_client:
        factory = ClientFactory(ClientConfig(streaming=False, httpx_client=http_client))
        client = await factory.create_from_url(f"{PUBLIC_URL}/agents/{agent_id}")
        payload = json.dumps({"transaction": transaction, "artifacts": artifacts})
        request = SendMessageRequest(message=new_text_message(payload, role=Role.ROLE_USER))
        async for response in client.send_message(request):
            if response.HasField("message"):
                data = json.loads(get_message_text(response.message))
                if "error" in data: raise RuntimeError(data["error"])
                return data
    raise RuntimeError(f"{agent_id} returned no A2A message")

def governed_tool_log(run: dict, agent_id: str, summary: str) -> None:
    """Record each specialist's concrete tool contract at the Zone 3 boundary."""
    definition = BY_ID[agent_id]
    for tool in definition.tools:
        store.audit(run["id"], agent_id, tool.name, tool.purpose, tool.access, summary, now())
    event(run, "tool", f"{definition.name} · Controlled tools", f"Authorized read tools: {', '.join(definition.tool_names)}. Every invocation contract is logged.")

def _source_quote(transaction: dict, terms: tuple[str, ...] = ()) -> str:
    """Return one bounded primary-source excerpt for the observable UI trace."""
    document = next((d for d in transaction["documents"] if any(term in d["text"].lower() for term in terms)), None)
    document = document or next((d for d in transaction["documents"] if d["name"] == "Purchase Agreement"), transaction["documents"][0])
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", document["text"]) if len(part.strip()) >= 35]
    sentence = next((part for part in sentences if any(term in part.lower() for term in terms)), sentences[0])
    if len(sentence) > 220: sentence = sentence[:217].rstrip() + "…"
    sentence = sentence.rstrip(".")
    return f'Quoted source: “{sentence}.” — {citation(document, sentence)}.'


def format_readiness_response(risk: dict, transaction: dict) -> str:
    """Turn a validated Risk artifact into a clear, presentation-ready explanation."""
    lane = risk["lane"]
    next_action = risk.get("modelNextAction") or risk["nextAction"]

    if lane == "GREEN":
        return (
            "Why this is Green\n"
            "The Risk Agent recommends Green because the retained packet is consistent and the review found no unresolved material conflict or missing evidence that would require the workflow to stop.\n\n"
            "What the agents confirmed\n"
            "• The purchase agreement and amendment are signed and consistent.\n"
            "• The deposit is confirmed by escrow.\n"
            "• Financing, required disclosures, title review, and contingency records are present without a retained blocker.\n\n"
            "What this means\n"
            "Doorlight found no reason to hold the packet, but Green is still a recommendation—not permission to fund, record, or close the transaction. An authorized person must perform the final review.\n\n"
            f"Next step\n{next_action.rstrip('.')}"
        )

    if lane == "AMBER":
        deposit = transaction.get("depositAmount", 0)
        return (
            "Why this is Amber\n"
            "The Risk Agent recommends Amber because escrow has not confirmed receipt of the earnest-money deposit. The Deposit Receipt specifically says confirmation is still pending.\n\n"
            "What is missing\n"
            f"The file has a buyer-side delivery reference, but it does not yet prove that escrow received the full ${deposit:,.0f} earnest-money deposit. The received amount, receipt time, and escrow confirmation number are still unverified.\n\n"
            "Why this is not Red\n"
            "The agents did not find a conflicting purchase price, missing agreement signature, unresolved title lien, or another material contract problem. This is a limited follow-up item, so the transaction needs human review rather than a full stop.\n\n"
            f"Source\n{risk['evidence'][0]}\n\n"
            f"Next step\n{next_action.rstrip('.')}"
        )

    findings = "\n".join(f"• {finding.rstrip('.')}" for finding in risk.get("findings", []))
    return (
        "Why this is Red\n"
        "The Risk Agent recommends Red because the retained documents contain multiple material blockers. The workflow cannot recommend readiness until all of them are resolved.\n\n"
        "What the agents found\n"
        f"{findings}\n\n"
        "Why this matters\n"
        "The packet does not establish a fully executed controlling agreement, a clear title path, or one resolved purchase price. Doorlight therefore holds all closing-related actions for broker or appropriate expert review.\n\n"
        f"Next step\n{next_action.rstrip('.')}"
    )

def live_agent_report(agent_id: str, output: dict, transaction: dict) -> list[str]:
    """Four plain-language sentences for the Live Overview, never chain-of-thought."""
    if agent_id == "transaction-intake-agent":
        parties = transaction["parties"]
        return [f"Created one starting record for transaction {transaction['id']} at {transaction['property']}.", f"Recorded {parties['buyer']} as buyer and {parties['seller']} as seller, together with the supplied agents and transaction side.", f"Organized the financing type, purchase timeline, and important dates so every later specialist uses the same case details.", "Passed that normalized record forward without deciding whether the transaction is compliant or ready."]
    if agent_id == "policy-agent":
        policy = output.get("policy", {})
        requirements = len(policy.get("requirements", []))
        return [f"Selected {policy.get('id', 'the supplied review policy')} version {policy.get('version', '')}.", f"Built an {requirements}-item review checklist because this is a California buyer-side resale using conventional financing.", "Defined which agreement, deposit, financing, disclosure, title, contingency, and closing evidence the review must check.", "Set the review rules only; the final Green, Amber, or Red recommendation remains with the Risk Agent."]
    if agent_id == "document-intake-agent":
        inventory = output.get("inventory", [])
        vision = output.get("visionOcr", {})
        page_count = sum(document.get("pageCount", 1) for document in transaction["documents"])
        vision_status = vision.get("status", "not reported").replace("_", " ").lower()
        return [f"Created an inventory of {len(inventory)} retained documents covering {page_count} source pages.", "Classified each record, preserved its version, and created a source fingerprint so duplicates or later changes can be detected.", f"Ran the bounded local vision/OCR preflight; its status was {vision_status}. The preserved page text remains the evidence source.", "Returned the organized document inventory to Light without deciding what the documents legally mean."]
    if agent_id == "evidence-agent":
        return ["Searched the retained source pages for transaction facts, exception language, and missing confirmations.", "Kept direct document statements separate from later compliance or risk conclusions.", "Attached the document name, version, and exact source page to every material finding.", _source_quote(transaction, ('pending confirmation', 'seller signature missing', 'requires written payoff', 'no superseding amendment'))]
    if agent_id == "reconciliation-agent":
        exceptions = [
            finding for finding in output.get("findings", [])
            if not finding.lower().startswith("no unresolved")
            and any(term in finding.lower() for term in ("conflict", "exception", "signature is missing"))
        ]
        conflict_text = f"Found {len(exceptions)} unresolved material exception{'s' if len(exceptions) != 1 else ''}." if exceptions else "Found no unresolved conflict between the controlling agreement and later amendments."
        return ["Placed the purchase agreement, amendment, and any counteroffer into their chronological order.", "Compared the parties, property, signatures, purchase price, title items, and important dates across those records.", f"{conflict_text} A difference was carried forward only when a later signed record did not clearly resolve it.", _source_quote(transaction, ('seller signature missing', 'requires written payoff', 'no superseding amendment', 'closing date'))]
    if agent_id == "compliance-agent":
        evaluations = output.get("evaluations", [])
        example = next((item for item in evaluations if item.get("status") != "SATISFIED"), evaluations[0] if evaluations else None)
        counts = {status: sum(item.get("status") == status for item in evaluations) for status in ("SATISFIED", "PARTIAL", "MISSING", "CONTRADICTORY", "HUMAN_JUDGMENT_REQUIRED")}
        source = example.get("evidence", ["No cited source"])[0] if example else "No cited source"
        example_text = f"The first open requirement was {example['requirement']}, recorded as {example['status']} from {source}." if example else "No open checklist requirement was found."
        return ["Checked every selected policy requirement against the cited evidence returned by the earlier agents.", f"Recorded {counts['SATISFIED']} satisfied, {counts['PARTIAL']} partial, {counts['MISSING']} missing, {counts['CONTRADICTORY']} contradictory, and {counts['HUMAN_JUDGMENT_REQUIRED']} requiring human judgment.", example_text, "Returned the checklist results without choosing the final risk lane."]
    if agent_id == "risk-agent":
        lane = output.get("lane", "unrated")
        return ["Reviewed the cited evidence, reconciled conflicts, and requirement-by-requirement checklist as one completed package.", f"Issued an evidence-backed {lane} recommendation: {output.get('summary', 'the risk result was recorded')}", f"Explained why the issue belongs in that lane and what would change the decision: {output.get('whatWouldChange', 'new verified evidence would be required')}", f"Required next step: {output.get('nextAction', 'send the result for authorized human review')}"]
    return ["Created a specialist result for this transaction.", "Used only the permitted local tools.", "Recorded the result for the other stages.", "Returned a validated artifact to the Orchestrator."]

def route_follow_up(prompt: str) -> str | None:
    p = prompt.lower()
    mapping = {"evidence": "evidence-agent", "signature": "evidence-agent", "document": "document-intake-agent", "ocr": "document-intake-agent", "policy": "policy-agent", "checklist": "compliance-agent", "compliance": "compliance-agent", "reconcil": "reconciliation-agent", "conflict": "reconciliation-agent", "counteroffer": "reconciliation-agent", "title": "reconciliation-agent", "risk": "risk-agent", "amber": "risk-agent", "green": "risk-agent", "red": "risk-agent", "party": "transaction-intake-agent", "intake": "transaction-intake-agent", "escrow": "transaction-intake-agent", "lender": "transaction-intake-agent"}
    return next((agent for word, agent in mapping.items() if word in p), None)

def is_full_workflow_request(prompt: str) -> bool:
    p = prompt.lower()
    return any(phrase in p for phrase in ("run the full", "run a full", "run all agents", "full workflow", "assess readiness", "ready to close", "is transaction", "is the transaction ready", "is this ready", "is it ready", "closing readiness", "analyze the transaction"))

def needs_live_overview(prompt: str, full_workflow: bool) -> bool:
    """Only show the execution trace when it helps explain a case/data operation."""
    if full_workflow:
        return True
    if is_agent_overview_question(prompt):
        return False
    p = prompt.lower()
    role_words = ("what about", "what do", "what can", "your role", "your tools", "what did", "tell me about")
    if any(word in p for word in role_words):
        return False
    return any(word in p for word in ("price", "deposit", "signature", "document", "title", "lien", "date", "deadline", "buyer", "seller", "property", "apn", "escrow", "risk", "red", "amber", "green"))

async def run_workflow(run: dict) -> None:
    transaction = get_transaction(run["caseId"]); artifacts: dict[str, dict] = {}
    try:
        event(run, "control", "Input & Event Normalization", f"Standardized {run['normalizedInput']['source']} as {run['intent']} for transaction {run['caseId']}; attached session, timestamp, and transaction metadata.")
        event(run, "assistant", "Light", "I’m checking the authorized transaction context now."); save(run)
        conversational = bool(run.get("followUp"))
        direct_agent = run.get("targetAgent") in BY_ID
        target = run.get("targetAgent") if direct_agent else None
        # Light remains the responder in Orchestrator mode. It can explain the
        # agent catalog and source packet without impersonating a specialist.
        stages = [target] if direct_agent else ([] if conversational else [a.id for a in AGENTS])
        planned = BY_ID[target].name if direct_agent else ("Light's plain-English case guide" if conversational else "the seven diagram-defined specialist stages")
        event(run, "control", "Conversation Context & Planner", f"Loaded the active case, normalized request, scoped retained documents, and current workflow context. Intent {run['intent']} uses {planned}; peer agents remain sequenced only by the Orchestrator."); save(run)
        for agent_id in stages:
            definition = BY_ID[agent_id]
            event(run, "agent", f"{definition.name} · A2A", f"{definition.description}", "active"); save(run)
            governed_tool_log(run, agent_id, definition.description)
            output = await invoke_agent(agent_id, transaction, artifacts)
            artifacts[agent_id] = output; store.save_artifact(run["id"], agent_id, output, now())
            active_event = next(item for item in reversed(run["events"]) if item["phase"] == "agent" and item["state"] == "active")
            active_event["state"] = "complete"
            overview = live_agent_report(agent_id, output, transaction)
            active_event["detail"] = " ".join(overview)
            active_event["overview"] = overview
            active_event["tools"] = list(definition.tool_names)
            save(run)
        risk = artifacts.get("risk-agent")
        if risk and not conversational:
            model_result = await risk_recommendation(run["provider"], run["request"], risk)
            if model_result and model_result["lane"] == risk["lane"]:
                risk = {**risk, "modelSummary": model_result["summary"], "modelNextAction": model_result["nextAction"]}
                artifacts["risk-agent"] = risk
                event(run, "agent", "Risk Agent · Model synthesis", "Selected model returned a validated recommendation grounded in the specialist evidence.")
            else:
                event(run, "agent", "Risk Agent · Verified artifact", "Selected model was unavailable, invalid, or contradicted decisive evidence; retained the evidence-validated Risk Agent artifact.")
            run["lane"] = risk["lane"]
            # Green and Amber artifacts may include an annotated retained page.
            # It is presentation evidence, not a new source or model conclusion.
            if risk.get("visualEvidence"):
                run["visualEvidence"] = risk["visualEvidence"]
            review = risk["lane"] != "GREEN"
            decision = "HUMAN_REVIEW_REQUIRED" if review else "ALLOWED_LOCAL_ACTION"
            event(run, "control", "Zone 3 · Permission Check", f"{risk['lane']} recommendation: {risk['summary']} {decision.replace('_', ' ').title()}.")
            store.audit(run["id"], "orchestrator", "local_workflow_action", "Create local task/reminder/draft only", decision, risk["nextAction"], now())
            commission = commission_calculation(transaction)
            closing = closing_control(transaction, risk)
            communication = communication_draft(transaction, risk)
            for service, result in (("commission_calculator", commission), ("closing_control", closing), ("communication_draft", communication)):
                store.audit(run["id"], "orchestrator", service, "Diagram-aligned local controlled service", result["status"], result["summary"], now())
                event(run, "control", f"Stage 8 · {service.replace('_', ' ').title()}", result["summary"])
            run["stage8"] = {"commission": commission, "closing": closing, "communication": communication}
            run["status"] = "AWAITING_HUMAN" if review else "COMPLETE"
            run["final"] = format_readiness_response(risk, transaction)
        elif conversational:
            selected = artifacts.get(stages[-1], {}) if stages else {}
            responder = stages[-1] if stages else "orchestrator"
            run["status"] = "COMPLETE"
            run["final"] = answer_follow_up(run["request"], responder, transaction, selected, direct=direct_agent)
        else:
            selected = artifacts[stages[-1]]
            run["status"] = "COMPLETE"; run["final"] = f"{BY_ID[stages[-1]].name} — {selected['summary']} Key findings: {'; '.join(selected['findings'])}. Sources: {'; '.join(selected['evidence'])}. Next: {selected['nextAction']}"
        event(run, "result", "Light", run["final"]); save(run)
    except Exception as exc:
        run["status"] = "FAILED"; run["final"] = f"The A2A agent network could not complete this request. {exc}"
        event(run, "error", "A2A Run Failed", str(exc), "blocked"); event(run, "result", "Light", run["final"], "blocked"); save(run)

async def ollama_health() -> tuple[str, str]:
    for host in ollama_hosts():
        try:
            async with httpx.AsyncClient(timeout=1.2) as client:
                if (await client.get(f"{host}/api/tags")).is_success: return "CONNECTED", host
        except httpx.HTTPError: pass
    return "UNAVAILABLE", " or ".join(ollama_hosts())

@app.get("/api/health")
async def health():
    ollama, host = await ollama_health()
    # GEMINI_API_KEY is optional; absence must report UNAVAILABLE, never crash health.
    configured_keys = [os.getenv("GEMINI_API_KEY") or "", *os.getenv("GEMINI_API_KEYS", "").split(",")]
    keys = [key.strip() for key in configured_keys if key and key.strip()]
    return {"gemini": "CONFIGURED" if keys else "UNAVAILABLE", "geminiModel": os.getenv("GEMINI_TEXT_MODEL", "gemini-3.6-flash"), "geminiKeyCount": len(keys), "geminiAvailableKeyCount": len(keys), "ollama": ollama, "ollamaHost": host, "ollamaHint": None if ollama == "CONNECTED" else "Start Ollama in WSL or expose Windows Ollama on 0.0.0.0:11434.", "ollamaModel": os.getenv("OLLAMA_MODEL", "llama3.1:8b"), "ollamaVisionModel": os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")}
@app.get("/api/cases")
async def cases(): return list_cases()
@app.get("/api/transaction/{case_id}")
async def transaction(case_id: str):
    item = get_transaction(case_id)
    if not item: raise HTTPException(404, "Transaction not found")
    return item
@app.get("/api/visual-evidence/{case_id}/{filename}")
async def visual_evidence(case_id: str, filename: str):
    """Serve a cached annotated source page without touching Vite's public tree."""
    if not get_transaction(case_id) or Path(filename).name != filename:
        raise HTTPException(404, "Visual evidence was not found")
    image = CACHE_ROOT / case_id / filename
    if not image.is_file() or image.suffix != ".png":
        raise HTTPException(404, "Visual evidence was not found")
    return FileResponse(image, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
@app.get("/api/context-overview/{case_id}/{run_id}")
async def context_overview(case_id: str, run_id: str):
    item = get_transaction(case_id)
    if not item: raise HTTPException(404, "Transaction not found")
    run = store.get_run(run_id)
    if not run or run.get("caseId") != case_id:
        raise HTTPException(404, "Workflow run not found for this transaction")
    if not store.has_artifact(run_id, "document-intake-agent") or not store.has_artifact(run_id, "evidence-agent"):
        raise HTTPException(409, "Context Overview is available after a completed full workflow has produced Document Intake and Evidence artifacts.")
    return build_context_overview(item)
@app.get("/api/runs")
async def runs(): return store.list_runs()
@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    item = store.get_run(run_id)
    if not item: raise HTTPException(404, "Run not found")
    return item
@app.post("/api/runs", status_code=201)
async def create_run(request: RunRequest):
    if not request.request.strip(): raise HTTPException(400, "Enter a request for Light.")
    if not get_transaction(request.caseId): raise HTTPException(404, "Selected transaction case was not found.")
    target = request.targetAgent if request.targetAgent in BY_ID else None
    full_workflow = is_full_workflow_request(request.request) and target is None
    follow_up = not full_workflow
    session_id = request.sessionId or str(uuid.uuid4())
    normalized = normalize_input(request.request.strip(), request.caseId, session_id)
    run = {"id": str(uuid.uuid4()), "caseId": request.caseId, "sessionId": session_id, "provider": "GEMINI" if request.provider == "GEMINI" else "OLLAMA", "targetAgent": target, "followUp": follow_up, "showLive": needs_live_overview(request.request, full_workflow), "request": request.request.strip()[:1000], "intent": normalized["eventType"], "normalizedInput": normalized, "status": "RUNNING", "events": [], "createdAt": now()}
    save(run); asyncio.create_task(run_workflow(run)); return run
