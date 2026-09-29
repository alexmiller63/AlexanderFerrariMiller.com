#!/usr/bin/env python3
"""One-shot diagnostic: zoom in on the Venus-Sun 1-degree transition."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tests/test_planet_finder_w02_conjunction.py")
text = TARGET.read_text(encoding="utf-8")
old = "    separations = [2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0]"
new = "    separations = [1.10, 1.09, 1.08, 1.07, 1.06, 1.05, 1.04, 1.03, 1.02, 1.01, 1.00]"
if text.count(old) != 1:
    raise SystemExit("Safety stop: current Venus-Sun ladder did not match exactly once")
TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Diagnostic Venus-Sun ladder zoomed to 1.10, 1.09, ... 1.00 degrees. "
    "Conjunction threshold remains 0.1deg; solver geometry and search behavior are unchanged. "
    "Repair Once is now OFF."
)
