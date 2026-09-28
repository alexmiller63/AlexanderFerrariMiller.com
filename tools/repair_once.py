#!/usr/bin/env python3
"""One-shot diagnostic: restore sequential candidate lattice ordering."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_geometry.py")
text = TARGET.read_text(encoding="utf-8")
old = '''    quarter_step = LABEL_LENGTH * 0.25\n    # Cover the full legal tangential interval before filling it in.  This is\n    # a deterministic coarse-to-fine ordering of exactly the same 0..8 shells:\n    # endpoints, center, half points, quarter points, then remaining eighths.\n    # The +/- order remains symmetric.  No candidate is added or removed.\n    shell_order = (8, 0, 4, 2, 6, 1, 3, 5, 7)\n    for shell in shell_order:\n'''
new = '''    quarter_step = LABEL_LENGTH * 0.25\n    for shell in range(9):\n'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: broad-to-fine lattice count={text.count(old)}; expected 1")
TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")

me = Path(__file__)
text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")
print("Restored sequential candidate lattice ordering for regression diagnostic; Repair Once is now OFF.")
