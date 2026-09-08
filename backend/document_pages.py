"""Deterministic pagination shared by API metadata and the asset renderer."""
from __future__ import annotations

import textwrap

LINE_CAPACITY = 48


def wrapped_lines(body: str, width: int = 92) -> list[str]:
    lines: list[str] = []
    for raw in body.splitlines() or [""]:
        if not raw.strip():
            lines.append("")
        elif " | " in raw:
            lines.extend(textwrap.wrap(raw, width=width, subsequent_indent="    ", break_long_words=False) or [""])
        else:
            lines.extend(textwrap.wrap(raw, width=width, break_long_words=False, break_on_hyphens=False) or [""])
    return lines


def paginate_blocks(blocks: list[dict], width: int = 92) -> list[list[dict]]:
    """Split every block without truncation; continuation blocks are explicit."""
    pages: list[list[dict]] = [[]]
    used = 0
    for block in blocks:
        lines = wrapped_lines(block["body"], width)
        first = True
        while lines:
            heading_cost = 3
            available = LINE_CAPACITY - used - heading_cost
            if available < 4:
                pages.append([]); used = 0; available = LINE_CAPACITY - heading_cost
            take = min(len(lines), available)
            chunk, lines = lines[:take], lines[take:]
            pages[-1].append({"heading": block["heading"] + (" — continued" if not first else ""), "lines": chunk})
            used += heading_cost + len(chunk) + 1
            first = False
            if lines:
                pages.append([]); used = 0
    return [page for page in pages if page]


def page_texts(blocks: list[dict]) -> list[str]:
    return ["\n\n".join(f"{b['heading'].upper()}\n" + "\n".join(b["lines"]) for b in page) for page in paginate_blocks(blocks)]


def page_for_phrase(document: dict, phrase: str) -> int:
    normalize = lambda value: " ".join(value.casefold().split())
    needle = normalize(phrase)
    for index, page in enumerate(document.get("sourcePages", []), 1):
        if needle in normalize(page.get("text", "")):
            return index
    return int(document.get("page", 1))
