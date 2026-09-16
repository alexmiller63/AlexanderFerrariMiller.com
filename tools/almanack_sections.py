#!/usr/bin/env python3
"""Stable numbered section identities for generated Almanack week pages."""
from __future__ import annotations

import re
from pathlib import Path

SECTION_ID_PREFIX = "almanack-section-"
SECTION_NAMES = {
    1: "top-navigation",
    2: "calendar",
    3: "ephemeris",
    4: "planet-finder",
    5: "sky-notes",
}


def section_open(number: int) -> str:
    name = SECTION_NAMES[number]
    return f'<div id="{SECTION_ID_PREFIX}{number}" data-almanack-section="{number}" data-almanack-section-name="{name}">'


def section_bounds(text: str, number: int, path: Path | None = None) -> tuple[int, int]:
    marker = f'id="{SECTION_ID_PREFIX}{number}"'
    marker_pos = text.find(marker)
    if marker_pos < 0:
        where = f" in {path}" if path is not None else ""
        raise RuntimeError(f"Missing Almanack section {number}{where}")

    start = text.rfind("<div", 0, marker_pos)
    open_end = text.find(">", marker_pos)
    if start < 0 or open_end < 0:
        raise RuntimeError(f"Malformed Almanack section {number}")

    token_re = re.compile(r"<div\b[^>]*>|</div>", re.I)
    depth = 1
    for match in token_re.finditer(text, open_end + 1):
        token = match.group(0).lower()
        if token.startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return open_end + 1, match.start()
    raise RuntimeError(f"Unclosed Almanack section {number}")


def replace_section_inner(text: str, number: int, replacement: str, path: Path | None = None) -> str:
    start, end = section_bounds(text, number, path)
    return text[:start] + replacement + text[end:]


def require_section(text: str, number: int, path: Path | None = None) -> None:
    section_bounds(text, number, path)
