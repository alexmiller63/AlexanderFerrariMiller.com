#!/usr/bin/env python3
"""One-shot diagnostic: lower conjunction threshold to 0.1 degree."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_geometry.py")
text = TARGET.read_text(encoding="utf-8")
old = "NEAR_CONJUNCTION_DEGREES = 1.0"
new = "NEAR_CONJUNCTION_DEGREES = 0.1"
if text.count(old) != 1:
    raise SystemExit("Safety stop: conjunction threshold did not match exactly once")
TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Diagnostic conjunction threshold changed from 1.0deg to 0.1deg. "
    "No geometry, alignment, candidate, or search rule changed. Repair Once is now OFF."
)
