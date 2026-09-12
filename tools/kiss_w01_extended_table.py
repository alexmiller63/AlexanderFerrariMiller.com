#!/usr/bin/env python3
"""One-time KISS edit for 2026-W01: put Extended data in the proven-good table shell."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "almanack" / "2026" / "W01" / "index.html"
TABLE = re.compile(r'<table class="[^"]*ephemeris[^"]*">.*?</table>', re.DOTALL)

text = PATH.read_text(encoding="utf-8")
matches = list(TABLE.finditer(text))
if len(matches) != 3:
    raise SystemExit(f"STOP: expected exactly 3 ephemeris tables, found {len(matches)}")

first, second, third = [m.group(0) for m in matches]
if first != second:
    raise SystemExit("STOP: tables 1 and 2 are not identical; nothing changed")
if not third.startswith('<table class="ephemeris extended-ephemeris">'):
    raise SystemExit("STOP: table 3 is not the expected old Extended table; nothing changed")

third_inner = re.fullmatch(r'<table class="ephemeris extended-ephemeris">(.*)</table>', third, re.DOTALL)
if not third_inner:
    raise SystemExit("STOP: could not isolate table 3 contents; nothing changed")

replacement = '<table class="ephemeris">' + third_inner.group(1) + '</table>'
new = text[:matches[1].start()] + replacement + text[matches[1].end():]

new_matches = list(TABLE.finditer(new))
if len(new_matches) != 3:
    raise SystemExit("STOP: post-edit table count is not 3; nothing changed")
if new_matches[0].group(0) != first:
    raise SystemExit("STOP: table 1 changed unexpectedly; nothing changed")
if new_matches[1].group(0) != replacement:
    raise SystemExit("STOP: table 2 verification failed; nothing changed")
if new_matches[2].group(0) != third:
    raise SystemExit("STOP: table 3 changed unexpectedly; nothing changed")

PATH.write_text(new, encoding="utf-8")
print("PASS: W01 table 2 now contains Ceres–Pluto in the plain ephemeris shell; tables 1 and 3 unchanged.")
