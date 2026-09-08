"""Create bounded, source-page visual evidence for Green and Amber results.

The highlight is an annotation over a retained synthetic page, never a replacement
for the page or a claim that the model located a real-world PDF coordinate.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .agents.base import citation
from .document_pages import paginate_blocks, page_for_phrase

PACKET_ROOT = Path("public/demo-packet")
CACHE_ROOT = Path("backend/.cache/visual-evidence")
WIDTH, HEIGHT = 1650, 2200


def _font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _body_start(layout: str) -> tuple[int, int]:
    """Mirror the document renderer's content start closely enough to mark a line."""
    left = 330 if layout in {"financial-table", "closing-table", "settlement-ledger", "condition-register"} else 105
    if layout in {"letter", "conditional-letter", "valuation-letter"}:
        return left, 503
    if layout in {"binder", "coverage-comparison"}:
        return left, 448
    if left == 330:
        return left, 238
    return left, 303


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _highlight_box(document: dict[str, Any], page_number: int, phrase: str) -> tuple[int, int, int, int]:
    """Locate the matching rendered line using the same block pagination as the page."""
    page = paginate_blocks(document["blocks"])[page_number - 1]
    left, y = _body_start(document["layout"])
    right = WIDTH - 105
    wanted = _normalize(phrase)
    wanted_terms = [term for term in re.findall(r"[a-z]{5,}", wanted)][:4]
    inspection_layouts = {"room-report", "inspection-report", "pest-report", "appointment-checklist"}
    table_layouts = {"financial-table", "closing-table", "settlement-ledger", "condition-register", "hazard-schedule", "association-matrix", "systems-matrix", "pest-report", "appointment-checklist"}
    for block in page:
        heading_y = y
        if wanted in _normalize(block["heading"]):
            return left - 16, heading_y - 14, right + 16, heading_y + 50
        y += 62
        signed = any(term in block["heading"].lower() for term in ("signature", "authorized lending", "seller response", "inspector /", "preparer certification", "issuing representative"))
        for line in block["lines"]:
            normalized_line = _normalize(line)
            # Prefer the exact retained sentence.  The fallback is deliberately
            # strict so a generic earlier reference to (for example) "deposit"
            # cannot steal the highlight from the actual missing-item sentence.
            is_match = wanted in normalized_line or (wanted_terms and sum(term in normalized_line for term in wanted_terms) >= min(3, len(wanted_terms)))
            height = 45 + 25 * max(0, len(line) // 86) if " | " in line and document["layout"] in table_layouts else (38 if signed else 30)
            if is_match:
                return left - 16, y - 13, right + 16, y + height + 10
            y += height
        y += 26
    # A safe fallback keeps the visual tied to the right page even if a phrase wraps.
    return left - 16, _body_start(document["layout"])[1] + 46, right + 16, _body_start(document["layout"])[1] + 128


def build_visual_evidence(transaction: dict[str, Any], document_name: str, phrase: str, lane: str, explanation: str) -> dict[str, str]:
    """Write and describe the annotated retained page used in a Green/Amber result."""
    document = next(item for item in transaction["documents"] if item["name"] == document_name)
    page = page_for_phrase(document, phrase)
    suffix = "" if page == 1 else f"-p{page}"
    source = PACKET_ROOT / transaction["id"] / f"{document['assetSlug']}{suffix}.png"
    marker = hashlib.sha256(f"v2|{document['sourceHash']}|{page}|{phrase}|{lane}".encode()).hexdigest()[:12]
    # Never write generated annotations into public/: Vite watches public files
    # during development, and that would force a browser reload mid-workflow.
    folder = CACHE_ROOT / transaction["id"]
    target = folder / f"{document['assetSlug']}-p{page}-{lane.lower()}-{marker}.png"
    if not target.exists():
        folder.mkdir(parents=True, exist_ok=True)
        image = Image.open(source).convert("RGBA")
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        box = _highlight_box(document, page, phrase)
        colors = {
            "GREEN": ((35, 123, 70, 95), (31, 105, 58, 255), "GREEN CONFIRMATION"),
            "AMBER": ((202, 133, 0, 105), (151, 95, 0, 255), "AMBER ITEM NEEDS FOLLOW-UP"),
            "RED": ((173, 29, 48, 105), (132, 17, 35, 255), "RED BLOCKER NEEDS RESOLUTION"),
        }
        color, border, label = colors[lane]
        draw.rounded_rectangle(box, radius=12, fill=color, outline=border, width=7)
        label_width = min(box[2] - box[0], 720)
        draw.rounded_rectangle((box[0], max(12, box[1] - 48), box[0] + label_width, max(12, box[1] - 48) + 42), radius=8, fill=border)
        draw.text((box[0] + 14, max(20, box[1] - 39)), label, font=_font(18, True), fill="white")
        Image.alpha_composite(image, overlay).convert("RGB").save(target, "PNG", optimize=True)
    return {
        "lane": lane,
        "title": "Confirmed Source Evidence" if lane == "GREEN" else "Source Item Needing Follow-Up",
        "explanation": explanation,
        "quote": phrase,
        "citation": citation(document, phrase),
        "imageUrl": f"/api/visual-evidence/{transaction['id']}/{target.name}?v={marker}",
        "originalImageUrl": f"/demo-packet/{transaction['id']}/{document['assetSlug']}{suffix}.png?v={document['sourceHash'][:10]}",
    }
