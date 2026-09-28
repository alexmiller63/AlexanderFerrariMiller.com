#!/usr/bin/env python3
"""Repair-once: make ordinary label candidate enumeration broad-to-fine.

This changes ordering only.  The canonical candidate set, legality tests, circular
lambda constraints, routing, collision rules, scoring, and caps are unchanged.
"""
from pathlib import Path

TARGET = Path("tools/planet_finder_geometry.py")
text = TARGET.read_text(encoding="utf-8")

old = '''    quarter_step = LABEL_LENGTH * 0.25\n    for shell in range(9):\n        shifts = (0.0,) if shell == 0 else (-shell * quarter_step, shell * quarter_step)\n        for shift in shifts:\n            for r in radii:\n                bx, by = xy(longitude, r)\n                x, y = bx + shift * tx, by + shift * ty\n                if any(math.hypot(x - ox, y - oy) < 1e-9 for ox, oy in offered):\n                    continue\n                offered.append((x, y))\n                yield x, y\n'''
new = '''    quarter_step = LABEL_LENGTH * 0.25\n    # Cover the full legal tangential interval before filling it in.  This is\n    # a deterministic coarse-to-fine ordering of exactly the same 0..8 shells:\n    # endpoints, center, half points, quarter points, then remaining eighths.\n    # The +/- order remains symmetric.  No candidate is added or removed.\n    shell_order = (8, 0, 4, 2, 6, 1, 3, 5, 7)\n    for shell in shell_order:\n        shifts = (0.0,) if shell == 0 else (-shell * quarter_step, shell * quarter_step)\n        for shift in shifts:\n            for r in radii:\n                bx, by = xy(longitude, r)\n                x, y = bx + shift * tx, by + shift * ty\n                if any(math.hypot(x - ox, y - oy) < 1e-9 for ox, oy in offered):\n                    continue\n                offered.append((x, y))\n                yield x, y\n'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: canonical lattice loop count={text.count(old)}; expected 1")
text = text.replace(old, new, 1)
TARGET.write_text(text, encoding="utf-8")
print("Reordered canonical candidate lattice broad-to-fine; candidate set and lambda legality unchanged.")
