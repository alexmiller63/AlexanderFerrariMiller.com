#!/usr/bin/env python3
"""One-shot: install the opt-in Venus DFS depth trace."""

from pathlib import Path
import runpy

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

patch = Path("tools/patch_planet_finder_venus_depth_trace.py")
if not patch.exists():
    raise SystemExit(f"Safety stop: missing {patch}")

runpy.run_path(str(patch), run_name="__main__")

me = Path(__file__)
self_source = me.read_text(encoding="utf-8")
arming_line = "ENABLED" + " = True"
lines = self_source.splitlines()
matches = [i for i, line in enumerate(lines) if line.strip() == arming_line]
if len(matches) != 1:
    raise SystemExit(f"Safety stop: arming line count={len(matches)}")
lines[matches[0]] = "ENABLED = False"
me.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("Venus DFS depth trace installed; Repair Once is OFF.")
