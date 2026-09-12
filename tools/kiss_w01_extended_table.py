#!/usr/bin/env python3
"""One-time KISS diagnostic for 2026-W01: change one copied-table header only."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "almanack" / "2026" / "W01" / "index.html"
TABLE = re.compile(r'<table class="[^"]*ephemeris[^"]*">.*?</table>', re.DOTALL)
SUN_HEADER = '<th><span class="ephemeris-symbol">☉&#xfe0e;</span> Sun</th>'
CERES_HEADER = '<th>Ceres</th>'

text = PATH.read_text(encoding="utf-8")
matches = list(TABLE.finditer(text))
if len(matches) != 2:
    raise SystemExit(f"STOP: expected exactly 2 ephemeris tables, found {len(matches)}; nothing changed")

first = matches[0].group(0)
second = matches[1].group(0)
if second.count(SUN_HEADER) != 1:
    raise SystemExit("STOP: copied table does not contain exactly one Sun header; nothing changed")

changed_second = second.replace(SUN_HEADER, CERES_HEADER, 1)
new = text[:matches[1].start()] + changed_second + text[matches[1].end():]

new_matches = list(TABLE.finditer(new))
if len(new_matches) != 2 or new_matches[0].group(0) != first:
    raise SystemExit("STOP: table 1 changed or table count changed; nothing changed")
if new_matches[1].group(0) != changed_second:
    raise SystemExit("STOP: table 2 change did not verify; nothing changed")

PATH.write_text(new, encoding="utf-8")
print("PASS: table 1 unchanged; table 2 first header is plain Ceres with no glyph.")
