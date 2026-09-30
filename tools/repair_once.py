#!/usr/bin/env python3
"""One-shot harness repair: run only the fast W36 diagnostic test.

This changes only the AA- Test Planet Finder Conjunctions workflow command.
It prevents the diagnostic workflow from continuing through the full ladder
after test_00_fast_w36_venus_dead_end finishes. Production solver behavior is
unchanged.
"""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

WORKFLOW = Path(".github/workflows/test-planet-finder-conjunctions.yml")
text = WORKFLOW.read_text(encoding="utf-8")
old = "run: python -m pytest -q -s tests/test_planet_finder_ultimate_ladders.py"
new = "run: python -m pytest -q -s tests/test_planet_finder_ultimate_ladders.py::test_00_fast_w36_venus_dead_end"
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: workflow pytest anchor count={text.count(old)}; expected 1")
WORKFLOW.write_text(text.replace(old, new, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")
print("AA- Test Planet Finder Conjunctions now runs only the fast W36 diagnostic. Repair Once is now OFF.")
