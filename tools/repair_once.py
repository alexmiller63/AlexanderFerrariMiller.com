#!/usr/bin/env python3
"""One-shot repair: apply the prepared conjunction wide-to-narrow patch."""
from pathlib import Path
import runpy

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

patch = Path("tools/patch_planet_finder_canonical_lattice.py")
if not patch.exists():
    raise SystemExit(f"Safety stop: missing prepared patch {patch}")

runpy.run_path(str(patch), run_name="__main__")

me = Path(__file__)
text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")
print("Applied conjunction wide-to-narrow search patch; Repair Once is now OFF.")
