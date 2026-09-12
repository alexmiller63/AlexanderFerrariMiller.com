#!/usr/bin/env python3
"""One-time KISS diagnostic for 2026-W01: make all three ephemeris tables identical."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "almanack" / "2026" / "W01" / "index.html"
TABLE = re.compile(r'<table class="[^"]*ephemeris[^"]*">.*?</table>', re.DOTALL)

text = PATH.read_text(encoding="utf-8")
matches = list(TABLE.finditer(text))
if len(matches) != 3:
    raise SystemExit(f"STOP: expected exactly 3 ephemeris tables, found {len(matches)}")

first = matches[0].group(0)
# KISS means KISS: table 1 is the known-good control.  Do not reinterpret,
# restyle, reclass, or transplant data.  Copy its exact bytes twice.
new = text[:matches[0].end()] + text[matches[0].end():matches[1].start()] + first + text[matches[1].end():matches[2].start()] + first + text[matches[2].end():]

new_matches = list(TABLE.finditer(new))
if len(new_matches) != 3:
    raise SystemExit("STOP: post-edit table count is not 3; nothing changed")
if not all(m.group(0) == first for m in new_matches):
    raise SystemExit("STOP: the three tables are not byte-for-byte identical; nothing changed")

PATH.write_text(new, encoding="utf-8")
print("PASS: W01 has 3 byte-for-byte identical copies of table 1.")
