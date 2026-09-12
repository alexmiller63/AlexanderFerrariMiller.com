#!/usr/bin/env python3
"""Trivial KISS edit for 2026-W01: change only table 2's first heading cell to plain Ceres."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "almanack" / "2026" / "W01" / "index.html"
TABLE = re.compile(r'<table class="[^"]*ephemeris[^"]*">.*?</table>', re.DOTALL)
FIRST_TH = re.compile(r'<th>.*?</th>', re.DOTALL)

text = PATH.read_text(encoding="utf-8")
matches = list(TABLE.finditer(text))
if len(matches) != 3:
    raise SystemExit(f"STOP: expected exactly 3 ephemeris tables, found {len(matches)}")

first, second, third = [m.group(0) for m in matches]
new_second, count = FIRST_TH.subn('<th>Ceres</th>', second, count=1)
if count != 1:
    raise SystemExit("STOP: could not replace exactly one heading cell in table 2")
if new_second == second:
    raise SystemExit("STOP: table 2 did not change")

new = text[:matches[1].start()] + new_second + text[matches[1].end():]
new_matches = list(TABLE.finditer(new))
if len(new_matches) != 3:
    raise SystemExit("STOP: post-edit table count changed")
if new_matches[0].group(0) != first:
    raise SystemExit("STOP: table 1 changed unexpectedly")
if new_matches[2].group(0) != third:
    raise SystemExit("STOP: table 3 changed unexpectedly")
if not new_matches[1].group(0).startswith('<table class="ephemeris"><thead><tr><th>Ceres</th>'):
    raise SystemExit("STOP: table 2 first heading is not exactly Ceres")

PATH.write_text(new, encoding="utf-8")
print("PASS: changed only table 2 first heading cell to plain Ceres.")

# Trigger KISS workflow run.
