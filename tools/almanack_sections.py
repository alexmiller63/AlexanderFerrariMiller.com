#!/usr/bin/env python3
"""Stable numbered section identities for generated Almanack week pages."""
from __future__ import annotations

import re
from pathlib import Path

from almanack_paths import PAGE_TYPES

SECTION_ID_PREFIX = "almanack-section-"
ALMANACK_TYPES = PAGE_TYPES


def section_open(number: int) -> str:
    return f'<div id="{SECTION_ID_PREFIX}{number}" data-almanack-section="{number}">'


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
    if f'id="{SECTION_ID_PREFIX}{number}"' not in text:
        # Preserved weeks can predate numbered sections. Upgrade only the
        # requested legacy block, retaining Calendar, finders and navigation.
        legacy = {
            3: (r'<h3>Weekly Solar-System Ephemeris</h3>',
                r'<div class="bayer-toggle-wrap section-notation-toggle" data-notation-target="finder">'),
            5: (r'<h3>Sky Notes?</h3>', r'<h3>Chart</h3>'),
        }
        if number in legacy:
            opening, closing = legacy[number]
            starts = list(re.finditer(opening, text))
            ends = list(re.finditer(closing, text))
            if len(starts) == len(ends) == 1 and starts[0].end() <= ends[0].start():
                return (text[:starts[0].start()] + section_open(number) + replacement
                        + '</div>\n' + text[ends[0].start():])
    start, end = section_bounds(text, number, path)
    return text[:start] + replacement + text[end:]


def require_section(text: str, number: int, path: Path | None = None) -> None:
    section_bounds(text, number, path)
