#!/usr/bin/env python3
"""One-shot repair: apply the current conjunction blob recursion patch."""
from pathlib import Path
import runpy

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

runpy.run_path("tools/patch_planet_finder_canonical_lattice.py", run_name="__repair_patch__")

me = Path(__file__)
me.write_text(me.read_text(encoding="utf-8").replace("ENABLED = True", "ENABLED = False", 1), encoding="utf-8")
print("Applied conjunction blob recursion repair; Repair Once is now OFF.")
