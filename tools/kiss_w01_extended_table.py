#!/usr/bin/env python3
"""One-time KISS edit for 2026-W01: put the real Extended table in the proven-good plain ephemeris shell."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "almanack" / "2026" / "W01" / "index.html"
TABLE = re.compile(r'<table class="[^"]*ephemeris[^"]*">.*?</table>', re.DOTALL)
PLAIN = re.compile(r'<table class="ephemeris">(.*)</table>', re.DOTALL)
EXTENDED = re.compile(r'<table class="ephemeris extended-ephemeris">(.*)</table>', re.DOTALL)

text = PATH.read_text(encoding="utf-8")
matches = list(TABLE.finditer(text))
if len(matches) != 3:
    raise SystemExit(f"STOP: expected exactly 3 ephemeris tables, found {len(matches)}")

first, second, third = [m.group(0) for m in matches]

# W01 intentionally contains three tables during this KISS diagnostic:
#   1. Naked-eye planets in the ordinary ephemeris shell
#   2. a diagnostic copy of Extended targets in that same ordinary shell
#   3. the real Extended-targets table using the extended-ephemeris class
# Tables 1 and 2 therefore must NOT be compared for equality.
second_match = PLAIN.fullmatch(second)
if not second_match:
    raise SystemExit("STOP: table 2 is not the expected plain-shell diagnostic Extended table; nothing changed")
third_match = EXTENDED.fullmatch(third)
if not third_match:
    raise SystemExit("STOP: table 3 is not the expected real Extended table; nothing changed")

# The diagnostic and real Extended tables must contain the same markup; only
# their table class is allowed to differ. This proves the ordinary shell is
# being tested with exactly the same Extended data before we change the real one.
if second_match.group(1) != third_match.group(1):
    raise SystemExit("STOP: diagnostic and real Extended table contents differ; nothing changed")

replacement = '<table class="ephemeris">' + third_match.group(1) + '</table>'
new = text[:matches[2].start()] + replacement + text[matches[2].end():]

new_matches = list(TABLE.finditer(new))
if len(new_matches) != 3:
    raise SystemExit("STOP: post-edit table count is not 3; nothing changed")
if new_matches[0].group(0) != first:
    raise SystemExit("STOP: table 1 changed unexpectedly; nothing changed")
if new_matches[1].group(0) != second:
    raise SystemExit("STOP: table 2 changed unexpectedly; nothing changed")
if new_matches[2].group(0) != replacement:
    raise SystemExit("STOP: real Extended table verification failed; nothing changed")

PATH.write_text(new, encoding="utf-8")
print("PASS: W01 real Extended table now uses the proven-good plain ephemeris shell; tables 1 and 2 unchanged.")
