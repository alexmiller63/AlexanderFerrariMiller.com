#!/usr/bin/env python3
"""One-shot repair: make the W01 ladder's first rung genuinely easy.

The endpoint weeks and production Planet Finder are unchanged.  This only
widens the synthetic W01 easy geometry while preserving its shape: one
five-body alignment, one four-body alignment, and two ordinary bodies.
"""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tests/test_planet_finder_system.py")
text = TARGET.read_text(encoding="utf-8")

old = '''    ("easy", {"Sun": 0, "Mercury": 5, "Venus": 10, "Mars": 15, "Pluto": 20, "Saturn": 100, "Neptune": 107, "Ceres": 114, "Moon": 121, "Uranus": 180, "Jupiter": 240}),'''
new = '''    ("easy", {"Sun": 0, "Mercury": 20, "Venus": 40, "Mars": 60, "Pluto": 80, "Saturn": 140, "Neptune": 160, "Ceres": 180, "Moon": 200, "Uranus": 260, "Jupiter": 320}),'''

if text.count(old) != 1:
    raise SystemExit(f"Safety stop: W01 easy rung match count={text.count(old)}; expected 1")
text = text.replace(old, new, 1)
TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "W01 easy rung widened to 20-degree member spacing while preserving the "
    "five-body + four-body alignment structure. Exact W01/W02 and production code unchanged. "
    "Repair Once is now OFF."
)
