#!/usr/bin/env python3
"""One-time KISS diagnostic for 2026-W01: keep table 1 and one exact duplicate."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "almanack" / "2026" / "W01" / "index.html"
TABLE = re.compile(r'<table class="[^"]*ephemeris[^"]*">.*?</table>', re.DOTALL)

text = PATH.read_text(encoding="utf-8")
matches = list(TABLE.finditer(text))
if not matches:
    raise SystemExit("STOP: no ephemeris table found; nothing changed")

first = matches[0].group(0)

# KISS: preserve table 1 byte-for-byte and put exactly one byte-for-byte copy
# immediately after it. Remove every other ephemeris table.
prefix = text[:matches[0].start()]
suffix = text[matches[-1].end():]
new = prefix + first + first + suffix

new_matches = list(TABLE.finditer(new))
if len(new_matches) != 2:
    raise SystemExit(f"STOP: post-edit table count is {len(new_matches)}, not 2; nothing changed")
if new_matches[0].group(0) != first or new_matches[1].group(0) != first:
    raise SystemExit("STOP: the two tables are not byte-for-byte identical; nothing changed")

PATH.write_text(new, encoding="utf-8")
print("PASS: W01 has exactly 2 byte-for-byte identical copies of table 1.")
