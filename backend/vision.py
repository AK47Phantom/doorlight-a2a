"""Local Qwen vision/OCR adapter for retained synthetic document page images."""
from __future__ import annotations
import base64, hashlib, json, os, textwrap
from pathlib import Path
from typing import Any
import httpx
from PIL import Image, ImageDraw, ImageFont
from .config import ollama_hosts

CACHE_DIR = Path("backend/.cache")

def _packet_fingerprint(transaction: dict) -> str:
    joined = "|".join(document.get("sourceHash", "") for document in transaction["documents"])
    return hashlib.sha256(joined.encode()).hexdigest()[:12]

def _font(size: int):
    try: return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError: return ImageFont.load_default()

def render_packet_contact_sheet(transaction: dict) -> Path:
    """Compose the pre-made packet PNG pages into the image sent to vision.

    This makes the MVP's OCR boundary demonstrable without claiming there are
    production PDFs or customer scans in the synthetic fixture.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fingerprint = _packet_fingerprint(transaction)
    path = CACHE_DIR / f"transaction-{transaction['id']}-document-contact-sheet-{fingerprint}.png"
    if path.exists(): return path
    columns, tile_width, tile_height, margin = 2, 700, 410, 22
    rows = (len(transaction["documents"]) + columns - 1) // columns
    image = Image.new("RGB", (columns * tile_width + (columns + 1) * margin, rows * tile_height + (rows + 1) * margin), "#fbfaf6")
    draw = ImageDraw.Draw(image); title_font = _font(15)
    for index, document in enumerate(transaction["documents"]):
        row, col = divmod(index, columns); left = margin + col * (tile_width + margin); top = margin + row * (tile_height + margin)
        draw.rectangle((left, top, left + tile_width, top + tile_height), outline="#252525", width=2, fill="#ffffff")
        asset = Path("public/demo-packet") / transaction["id"] / f"{document['assetSlug']}.png"
        if asset.exists():
            page = Image.open(asset).convert("RGB")
            # The top portion contains the source header and material excerpt;
            # it keeps the contact sheet readable and bounded for local vision.
            page = page.crop((0, 0, page.width, min(page.height, 930)))
            page.thumbnail((tile_width - 32, tile_height - 58))
            image.paste(page, (left + (tile_width - page.width) // 2, top + 42))
        else:
            draw.text((left + 16, top + 15), f"Missing generated page: {document['name']}", fill="#9a1b24", font=title_font)
        draw.text((left + 16, top + 15), f"RECORD {index + 1} | {document['name'].upper()} | {document['version']} | cover 1/{document.get('pageCount', 1)}", fill="#9a1b24", font=title_font)
    image.save(path, format="PNG", optimize=True)
    return path

async def vision_ocr_preflight(transaction: dict) -> dict[str, Any]:
    """Use qwen2.5vl on the contact sheet; cache its bounded OCR observation."""
    if os.getenv("DOORLIGHT_VISION_OCR", "1").lower() in {"0", "false", "off"}:
        return {"status": "DISABLED", "summary": "Vision OCR preflight is disabled by DOORLIGHT_VISION_OCR.", "observations": []}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"transaction-{transaction['id']}-vision-{_packet_fingerprint(transaction)}.json"
    if cache.exists():
        cached = json.loads(cache.read_text())
        if cached.get("status", "").startswith("COMPLETED"): return cached
    image_path = render_packet_contact_sheet(transaction)
    image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    prompt = ("Read the synthetic transaction document contact sheet. Return JSON only: "
              '{"summary":"at most 16 words","observations":["document: visible term","document: visible term","document: visible term"]}. '
              "Use exactly three observations, each under 12 words. Do not assess compliance or risk.")
    timeout = float(os.getenv("OLLAMA_VISION_TIMEOUT_SECONDS", "28"))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            for host in ollama_hosts():
                try:
                    response = await client.post(f"{host}/api/chat", json={
                        "model": os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b"), "stream": False, "format": "json", "keep_alive": "20m",
                        "options": {"temperature": 0, "num_predict": 140, "num_ctx": 8192},
                        "messages": [{"role": "user", "content": prompt, "images": [image_data]}],
                    })
                    response.raise_for_status()
                    content = response.json()["message"]["content"].strip()
                    try:
                        parsed = json.loads(content)
                        summary = str(parsed.get("summary", "Vision OCR preflight completed."))[:500]
                        observations = [str(item)[:400] for item in parsed.get("observations", [])][:8]
                        status = "COMPLETED"
                    except json.JSONDecodeError:
                        # A visible model response is still useful for intake; label its
                        # incomplete schema rather than falsely calling OCR unavailable.
                        summary, observations, status = content[:500], [], "COMPLETED_PARTIAL"
                    result = {"status": status, "model": os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:7b"), "summary": summary, "observations": observations, "image": str(image_path)}
                    cache.write_text(json.dumps(result)); return result
                except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError): continue
    except httpx.HTTPError: pass
    return {"status": "UNAVAILABLE", "summary": "Vision OCR preflight could not reach the configured local vision model; retained source text remains available.", "observations": []}
