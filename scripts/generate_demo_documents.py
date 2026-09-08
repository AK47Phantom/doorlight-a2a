"""Render complete fictional transaction records from the backend's source model."""
from __future__ import annotations
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.document_pages import paginate_blocks
from backend.domain import TRANSACTIONS

ROOT = Path("public/demo-packet")
WIDTH, HEIGHT = 1650, 2200
PAPER, INK, MUTED, RED, LINE = "#fffdfb", "#211d1e", "#625a5c", "#9f1830", "#d8cdcf"

def font(size: int, bold: bool = False):
    try: return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
    except OSError: return ImageFont.load_default()

F_TITLE, F_HEAD, F_BODY, F_SMALL, F_MICRO = font(38, True), font(21, True), font(21), font(16, True), font(14)
try: F_SIGN = ImageFont.truetype("DejaVuSans-Oblique.ttf", 22)
except OSError: F_SIGN = F_BODY
FINANCIAL = {"financial-table", "closing-table", "settlement-ledger", "condition-register"}
QUESTION = {"checkbox-form", "questionnaire", "hazard-schedule", "applicability-election", "fire-screen", "tax-schedule", "association-matrix", "systems-matrix"}
INSPECTION = {"room-report", "inspection-report", "pest-report", "appointment-checklist"}
TABLES = FINANCIAL | {"hazard-schedule", "association-matrix", "systems-matrix", "pest-report", "appointment-checklist"}

def palette(layout: str) -> tuple[str, str]:
    if layout in {"letter", "conditional-letter", "valuation-letter"}: return "#183754", "#eaf1f7"
    if layout in FINANCIAL: return "#2c4c42", "#eaf3ef"
    if layout in QUESTION: return "#5b3b65", "#f4edf6"
    if layout in INSPECTION: return "#8a4a12", "#fcf0e5"
    if layout in {"title-schedules", "instructions", "receipt", "verification-log", "vesting-worksheet"}: return "#254b63", "#eaf2f6"
    if layout in {"binder", "coverage-comparison"}: return "#24515d", "#e9f3f5"
    return RED, "#f8ecef"

def masthead(draw, document, transaction, number, count, accent, wash):
    layout = document["layout"]
    if layout in {"letter", "conditional-letter", "valuation-letter"}:
        draw.rectangle((0, 0, WIDTH, 235), fill=accent)
        draw.text((100, 68), "HARBOR COMMUNITY LENDING", font=F_TITLE, fill="white")
        draw.text((102, 128), "Residential Lending Operations · fictional correspondence", font=F_BODY, fill="#dce8f2")
        y = 295
    elif layout in {"binder", "coverage-comparison"}:
        draw.rectangle((70, 60, WIDTH-70, 230), fill=wash, outline=accent, width=3)
        draw.text((105, 90), "HARBOR COAST COVERAGE", font=F_TITLE, fill=accent)
        draw.text((108, 150), "FICTIONAL EVIDENCE · NO REAL COVERAGE", font=F_SMALL, fill=MUTED)
        y = 290
    elif layout in FINANCIAL:
        draw.rectangle((0, 0, 270, HEIGHT), fill=accent)
        draw.text((58, 84), "DL", font=font(54, True), fill="white")
        draw.text((58, 155), "FINANCIAL\nRECORD", font=F_SMALL, fill="#dce8e3", spacing=8)
        y = 80
    else:
        draw.rectangle((0, 0, WIDTH, 92), fill=accent)
        draw.text((80, 31), "DOORLIGHT DEMONSTRATION PACKET", font=F_SMALL, fill="white")
        draw.text((WIDTH-570, 31), "SYNTHETIC · NON-OPERATIVE · NOT FOR EXECUTION", font=F_SMALL, fill="white")
        y = 145
    left = 330 if layout in FINANCIAL else 105
    draw.text((left, y), document["name"].upper(), font=F_TITLE, fill=INK)
    y += 62
    draw.text((left, y), f"Transaction {transaction['id']}  ·  {document['version']}  ·  Page {number} of {count}", font=F_SMALL, fill=MUTED)
    y += 54
    draw.line((left, y, WIDTH-105, y), fill=accent, width=3)
    return y + 42

def table_row(draw, x, y, text, width, accent, wash, alternate):
    height = 45 + 25 * max(0, len(text) // 86)
    draw.rectangle((x, y, x+width, y+height), fill=wash if alternate else "white", outline=LINE, width=1)
    pieces = [part.strip() for part in text.split("|")]
    if len(pieces) > 1:
        column = width // len(pieces)
        for i, part in enumerate(pieces):
            draw.text((x+14+i*column, y+13), part[:48], font=F_MICRO if i else F_SMALL, fill=accent if i == 0 else INK)
    else: draw.text((x+14, y+13), text, font=F_BODY, fill=INK)
    return y + height

def draw_body(draw, document, page, y, accent, wash):
    layout = document["layout"]; left = 330 if layout in FINANCIAL else 105; right = WIDTH-105
    if layout in {"letter", "conditional-letter", "valuation-letter"}:
        draw.text((left, y), "DELIVERED ELECTRONICALLY", font=F_SMALL, fill=accent); y += 50
    for bi, block in enumerate(page):
        if layout in QUESTION:
            draw.rounded_rectangle((left, y-12, right, y+48), radius=8, fill=wash)
            draw.text((left+20, y+8), block["heading"].upper(), font=F_HEAD, fill=accent)
        elif layout == "title-schedules":
            draw.rectangle((left, y-10, left+560, y+44), fill=accent)
            draw.text((left+16, y+7), block["heading"].upper()[:55], font=F_SMALL, fill="white")
        elif layout in INSPECTION:
            draw.ellipse((left, y-6, left+40, y+34), fill=accent)
            draw.text((left+13, y+5), str(bi+1), font=F_MICRO, fill="white")
            draw.text((left+58, y+3), block["heading"].upper(), font=F_HEAD, fill=accent)
        else:
            draw.text((left, y+3), block["heading"].upper(), font=F_HEAD, fill=accent)
            draw.line((left, y+39, min(left+470, right), y+39), fill=accent, width=2)
        y += 62
        signed_block = any(term in block["heading"].lower() for term in ("signature", "authorized lending", "seller response", "inspector /", "preparer certification", "issuing representative"))
        for li, line in enumerate(block["lines"]):
            if " | " in line and layout in TABLES:
                y = table_row(draw, left, y, line, right-left, accent, wash, li % 2 == 0)
            else:
                if layout == "questionnaire" and line.lstrip()[:2].rstrip(".").isdigit():
                    draw.rectangle((left, y-4, right, y+27), fill=wash)
                if signed_block:
                    draw.line((left, y+30, right, y+30), fill=LINE, width=1)
                draw.text((left, y), line, font=F_SIGN if signed_block else F_BODY, fill=INK); y += 38 if signed_block else 30
        y += 26

def render(case_id: str, transaction: dict, document: dict):
    destination = ROOT / case_id; destination.mkdir(parents=True, exist_ok=True)
    # Remove only obsolete generated continuation images for this exact document.
    for stale in destination.glob(f"{document['assetSlug']}-p*.png"):
        stale.unlink()
    pages = paginate_blocks(document["blocks"]); accent, wash = palette(document["layout"]); images = []
    for number, page in enumerate(pages, 1):
        image = Image.new("RGB", (WIDTH, HEIGHT), PAPER); draw = ImageDraw.Draw(image)
        y = masthead(draw, document, transaction, number, len(pages), accent, wash)
        draw_body(draw, document, page, y, accent, wash)
        draw.line((105, HEIGHT-90, WIDTH-105, HEIGHT-90), fill=LINE, width=1)
        draw.text((105, HEIGHT-64), f"SOURCE {document['sourceHash'][:16].upper()} · PAGE {number}/{len(pages)}", font=F_MICRO, fill=MUTED)
        draw.text((WIDTH-600, HEIGHT-64), "ORIGINAL FICTIONAL WORK · NOT AN OFFICIAL OR LICENSED FORM", font=F_MICRO, fill=MUTED)
        images.append(image)
        suffix = "" if number == 1 else f"-p{number}"
        image.save(destination / f"{document['assetSlug']}{suffix}.png", "PNG", optimize=True)
    images[0].save(destination / f"{document['assetSlug']}.pdf", "PDF", resolution=150, save_all=True, append_images=images[1:])

if __name__ == "__main__":
    for case_id, transaction in TRANSACTIONS.items():
        for document in transaction["documents"]: render(case_id, transaction, document)
    print(f"Generated {sum(len(t['documents']) for t in TRANSACTIONS.values())} documents in {ROOT}")
