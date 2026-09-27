#!/usr/bin/env python3
"""One-shot repair: give conjunction routing the full quarter-label angular escape lattice."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

p = Path("tools/planet_finder_geometry.py")
s = p.read_text(encoding="utf-8")
old = '''        angular_step = (LABEL_LENGTH * 0.25) / max(radius, 1.0)
        offsets = (0.0,)
        if allow_angular_escape:
            offsets = (0.0, -angular_step, angular_step, -2.0 * angular_step, 2.0 * angular_step)
'''
new = '''        angular_step = (LABEL_LENGTH * 0.25) / max(radius, 1.0)
        offsets = (0.0,)
        if allow_angular_escape:
            # Conjunction labels use the same canonical quarter-label lattice
            # as label placement: 0, +/-0.25, ... +/-2.00 label lengths.
            # The previous +/-0.50 limit could leave an anchor trapped behind
            # its sibling label even though a clean first elbow existed farther
            # around the same route radius.
            offsets = (0.0,) + tuple(
                sign * shell * angular_step
                for shell in range(1, 9)
                for sign in (-1.0, 1.0)
            )
'''
if s.count(old) != 1:
    raise SystemExit(f"Safety stop: expected conjunction angular-offset marker once; found {s.count(old)}")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

me = Path(__file__)
me.write_text(me.read_text(encoding="utf-8").replace("ENABLED = True", "ENABLED = False", 1), encoding="utf-8")
print("Installed full conjunction angular escape lattice; Repair Once is now OFF.")
