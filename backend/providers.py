"""Optional model synthesis adapters. Tool evidence remains authoritative."""
from __future__ import annotations
import json, os
import httpx
from .config import ollama_hosts

async def risk_recommendation(provider: str, question: str, risk: dict) -> dict | None:
    """Ask the selected model to express—not replace—the source-backed risk recommendation.

    Invalid, unavailable, or quota-limited model responses deliberately return None;
    the verified specialist artifact stays intact instead of fabricating an answer.
    """
    # The model receives the already validated decision boundary, not every peer
    # artifact. This keeps local 8B-model latency predictable and prevents a long
    # final wording pass from making the completed workflow appear frozen.
    prompt = (
        "Return JSON only with lane, summary, and nextAction. "
        f"Keep lane exactly {risk['lane']}. Write two plain-English summary sentences that name the exact decisive facts and explain why they produce this lane. "
        "Write one concrete next action sentence. Do not use vague phrases such as 'administrative evidence remains open' without naming the missing item. "
        f"Question: {question[:300]}\n"
        f"Verified reason: {risk['summary'][:700]}\n"
        f"Verified evidence: {'; '.join(risk['evidence'][:4])}\n"
        f"Verified next action: {risk['nextAction'][:350]}"
    )
    try:
        if provider == "OLLAMA":
            response = None
            timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "15"))
            async with httpx.AsyncClient(timeout=timeout) as client:
                for host in ollama_hosts():
                    try:
                        candidate = await client.post(f"{host}/api/chat", json={
                            "model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"), "stream": False, "format": "json", "keep_alive": "20m",
                            "options": {"temperature": 0, "num_predict": 180, "num_ctx": 2048},
                            "messages": [{"role": "user", "content": prompt}],
                        })
                        candidate.raise_for_status(); response = candidate; break
                    except httpx.HTTPError: continue
            if response is None: return None
            content = response.json()["message"]["content"]
        else:
            key = os.getenv("GEMINI_API_KEY") or next((x.strip() for x in os.getenv("GEMINI_API_KEYS", "").split(",") if x.strip()), None)
            if not key: return None
            from google import genai
            client = genai.Client(api_key=key)
            response = await client.aio.models.generate_content(model=os.getenv("GEMINI_TEXT_MODEL", "gemini-3.6-flash"), contents=prompt, config={"response_mime_type": "application/json"})
            content = response.text or ""
        result = json.loads(content)
        if result.get("lane") not in {"GREEN", "AMBER", "RED"}: return None
        if not isinstance(result.get("summary"), str) or not isinstance(result.get("nextAction"), str): return None
        summary = result["summary"].strip().lower()
        required_terms = {
            "GREEN": ("blocker", "consistent", "complete", "ready"),
            "AMBER": ("escrow", "deposit", "receipt"),
            "RED": ("signature", "title", "lien", "price", "agreement"),
        }
        if len(summary) < 45 or not any(term in summary for term in required_terms[result["lane"]]): return None
        return result
    except Exception:
        return None
