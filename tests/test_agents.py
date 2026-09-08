from backend.agents import BY_ID
from backend.domain import get_transaction
import asyncio
import inspect
import os
from pathlib import Path
from backend.app import health
from backend.config import load_local_env, ollama_hosts
from backend.followups import answer_follow_up
from backend.app import format_readiness_response, is_full_workflow_request, live_agent_report, needs_live_overview

def run_all(case_id: str):
    previous = os.environ.get("DOORLIGHT_VISION_OCR")
    os.environ["DOORLIGHT_VISION_OCR"] = "0"
    try:
        transaction = get_transaction(case_id); artifacts = {}
        for agent in BY_ID.values():
            result = agent.run(transaction, artifacts)
            artifacts[agent.id] = asyncio.run(result) if inspect.isawaitable(result) else result
        return artifacts
    finally:
        if previous is None: os.environ.pop("DOORLIGHT_VISION_OCR", None)
        else: os.environ["DOORLIGHT_VISION_OCR"] = previous

def test_each_agent_has_a_distinct_prompt_and_tool_set():
    assert len(BY_ID) == 7
    assert len({agent.prompt for agent in BY_ID.values()}) == 7
    assert all(agent.tool_names for agent in BY_ID.values())

def test_demo_cases_have_evidence_backed_recommendations():
    green = run_all("48290")["risk-agent"]
    amber = run_all("48291")["risk-agent"]
    assert green["lane"] == "GREEN"
    assert amber["lane"] == "AMBER"
    blocked = run_all("48292")["risk-agent"]
    assert blocked["lane"] == "RED"
    assert any("Preliminary Title Report v1, page" in item for item in blocked["evidence"])
    assert "visualEvidence" not in green
    for result, lane in ((amber, "AMBER"), (blocked, "RED")):
        visual = result["visualEvidence"]
        assert visual["lane"] == lane
        assert visual["citation"] in {"Deposit Receipt v2, page 1", "Purchase Agreement v2, page 2"}
        assert visual["imageUrl"].startswith("/api/visual-evidence/")
        filename = visual["imageUrl"].split("/")[-1].split("?", 1)[0]
        assert any(Path("backend/.cache/visual-evidence").rglob(filename))


def test_compliance_uses_document_evidence_not_literal_document_titles():
    amber = run_all("48291")["compliance-agent"]
    statuses = {item["requirement"]: item["status"] for item in amber["evaluations"]}
    assert statuses["Agency disclosure"] == "SATISFIED"
    assert statuses["Deposit confirmation"] == "PARTIAL"
    assert statuses["Seller and hazard disclosures"] == "SATISFIED"
    assert statuses["Closing authorization"] == "HUMAN_JUDGMENT_REQUIRED"

def test_evidence_agent_does_not_return_compliance_checklist_language():
    result = BY_ID["evidence-agent"].run(get_transaction("48292"), {})
    assert any("Counteroffer v1, page" in item for item in result["findings"])
    assert "SATISFIED" not in " ".join(result["findings"])

def test_source_records_are_dense_paginated_and_share_page_text():
    for case_id in ("48290", "48291", "48292"):
        transaction = get_transaction(case_id)
        assert all(len(document["text"].split()) >= 500 for document in transaction["documents"])
        assert all(document["pageCount"] == len(document["sourcePages"]) >= 2 for document in transaction["documents"])
        assert all("FIELD REGISTER" not in document["text"] for document in transaction["documents"])

def test_execution_state_is_preserved_in_the_documents():
    complete = next(d for d in get_transaction("48290")["documents"] if d["name"] == "Purchase Agreement")
    blocked = next(d for d in get_transaction("48292")["documents"] if d["name"] == "Purchase Agreement")
    pending = next(d for d in get_transaction("48291")["documents"] if d["name"] == "Deposit Receipt")
    assert "/s/ Taylor Morgan" in complete["text"] and "/s/ Jamie Ellis" in complete["text"]
    assert "Seller signature missing" in blocked["text"] and "/s/ Jamie Ellis" not in blocked["text"]
    assert "Received amount: NOT CONFIRMED" in pending["text"]

def test_every_declared_source_page_and_pdf_was_rendered():
    root = Path("public/demo-packet")
    for case_id in ("48290", "48291", "48292"):
        for document in get_transaction(case_id)["documents"]:
            assert (root / case_id / f"{document['assetSlug']}.pdf").stat().st_size > 10_000
            for page in document["sourcePages"]:
                suffix = "" if page["number"] == 1 else f"-p{page['number']}"
                assert (root / case_id / f"{document['assetSlug']}{suffix}.png").stat().st_size > 10_000

def test_followup_answers_are_specific_to_the_agent_and_source_records():
    transaction = get_transaction("48292")
    signature_answer = answer_follow_up("Which documents need signatures?", "evidence-agent", transaction, {})
    risk_answer = answer_follow_up("Why is this red?", "risk-agent", transaction, run_all("48292")["risk-agent"])
    assert "seller signature is missing" in signature_answer.lower()
    assert "Purchase Agreement v2, page" in signature_answer
    assert "requires written payoff or release evidence" in risk_answer
    assert "no superseding amendment" in risk_answer.lower()
    assert is_full_workflow_request("Run a full readiness review.")
    assert not is_full_workflow_request("What is escrow?")

def test_orchestrator_agent_overviews_and_case_data_are_plain_english():
    transaction = get_transaction("48292")
    compliance = answer_follow_up("wt abt the compliance agent?", "compliance-agent", transaction, {})
    price = answer_follow_up("What is the purchase price?", "evidence-agent", transaction, {})
    direct = answer_follow_up("What did you do in this case and what tools do you have?", "compliance-agent", transaction, run_all("48292")["compliance-agent"], direct=True)
    assert "What it does:" in compliance and "Tools it uses:" in compliance
    assert "does not provide legal advice" in compliance
    assert "$925,000.00" in price and "$910,000" in price
    assert "Case 48292" in direct and "checklist tool" in direct

def test_shorthand_agent_questions_and_live_overview_rules_are_consistent():
    transaction = get_transaction("48291")
    overview = answer_follow_up("wt abt compliance?", "orchestrator", transaction, {})
    direct = answer_follow_up("wt abt u?", "transaction-intake-agent", transaction, run_all("48291")["transaction-intake-agent"], direct=True)
    assert overview.startswith("Light's Overview: Compliance Agent")
    assert "What it can answer:" in overview
    assert direct.startswith("Transaction Intake Agent — Case 48291")
    assert not needs_live_overview("What does the Evidence Agent do?", False)
    assert not needs_live_overview("What can u do?", False)
    assert needs_live_overview("What is the purchase price?", False)
    assert needs_live_overview("Run a full readiness review.", True)
    assert not is_full_workflow_request("Why is the risk amber?")
    assert needs_live_overview("Why is the risk amber?", False)

def test_orchestrator_never_impersonates_a_specialist_for_agent_questions():
    transaction = get_transaction("48292")
    agent_answer = answer_follow_up("What does the Evidence Agent do?", "orchestrator", transaction, {})
    light_answer = answer_follow_up("What can u do?", "orchestrator", transaction, {})
    assert agent_answer.startswith("Light's Overview: Evidence Agent")
    assert "I provide" not in agent_answer
    assert light_answer.startswith("Light's Overview")
    assert "direct specialist mode" in light_answer

def test_every_agent_can_explain_its_own_method_and_tools_in_direct_mode():
    transaction = get_transaction("48291")
    artifacts = run_all("48291")
    for agent_id in BY_ID:
        answer = answer_follow_up("How do you normally work and what tools do you use?", agent_id, transaction, artifacts[agent_id], direct=True)
        assert "How It Works" in answer
        assert "Tools used:" in answer
        assert "Boundary:" in answer
        assert "latest returned result" not in answer
    intake = answer_follow_up("How do you normally intake the documents, do you use OCR?", "transaction-intake-agent", transaction, artifacts["transaction-intake-agent"], direct=True)
    assert "does not perform document OCR" in intake
    assert "Document Intake Agent" in intake

def test_drawio_zone_three_parity_contract_is_documented_and_backed_by_core_tools():
    parity = Path("DRAWIO_WORKFLOW_PARITY.md").read_text()
    for phrase in ("A2A-only handoffs", "Evidence record", "Green / Amber / Red branch", "Communication and permissions"):
        assert phrase in parity
    assert {"vision_ocr_preflight", "duplicate_detector", "transaction_associator"}.issubset(set(BY_ID["document-intake-agent"].tool_names))
    assert {"checklist_tool", "requirement_evaluator"}.issubset(set(BY_ID["compliance-agent"].tool_names))
    assert {"risk_rubric", "recommendation_validator"}.issubset(set(BY_ID["risk-agent"].tool_names))

def test_live_agent_overviews_have_four_plain_language_sentences():
    transaction = get_transaction("48291")
    for agent_id, output in run_all("48291").items():
        overview = live_agent_report(agent_id, output, transaction)
        assert len(overview) == 4
        assert all(sentence.endswith((".", "…")) for sentence in overview)


def test_readiness_explanations_name_the_issue_and_next_step_in_plain_english():
    green = format_readiness_response(run_all("48290")["risk-agent"], get_transaction("48290"))
    amber = format_readiness_response(run_all("48291")["risk-agent"], get_transaction("48291"))
    red = format_readiness_response(run_all("48292")["risk-agent"], get_transaction("48292"))
    assert "The deposit is confirmed by escrow" in green
    assert "not permission to fund, record, or close" in green
    assert "$25,500 earnest-money deposit" in amber
    assert "Why this is not Red" in amber
    assert "seller signature" in red.lower()
    assert "written payoff or release evidence" in red
    assert "$925,000" in red and "$910,000" in red

def test_health_handles_an_absent_optional_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
    result = asyncio.run(health())
    assert result["gemini"] == "UNAVAILABLE"

def test_ollama_discovery_includes_localhost_and_uses_configured_host(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://10.0.0.20:11434/")
    assert ollama_hosts()[0] == "http://10.0.0.20:11434"
    assert "http://127.0.0.1:11434" in ollama_hosts()
