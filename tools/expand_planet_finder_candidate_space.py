#!/usr/bin/env python3
"""Mechanically expand Planet Finder candidate space without relaxing safety rules."""
from pathlib import Path

PATH = Path(__file__).with_name("planet_finder_geometry.py")
text = PATH.read_text(encoding="utf-8")
old = '''    quarter_step = LABEL_LENGTH * 0.25
    quarter_shifts = tuple(i * quarter_step for i in range(-8, 9))
    yield from offer(PREFERRED_LABEL_RADII, quarter_shifts)
    yield from offer(EXPANDED_LABEL_RADII, quarter_shifts)
'''
new = '''    quarter_step = LABEL_LENGTH * 0.25
    quarter_shifts = tuple(i * quarter_step for i in range(-8, 9))
    yield from offer(PREFERRED_LABEL_RADII, quarter_shifts)
    yield from offer(EXPANDED_LABEL_RADII, quarter_shifts)

    # Emergency crowded-chart expansion. Ordinary weeks encounter all nearby
    # candidates above first; these progressively longer tangential leaders are
    # considered only when compact placements cannot work. Keep every existing
    # collision, rim, obstacle, and leader-clearance rule unchanged.
    # Extend symmetrically left/right through +/-6 label lengths so a pathological
    # conjunction can spread labels around the available inner disk.
    long_shifts = tuple(
        sign * LABEL_LENGTH * scale
        for scale in (2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0)
        for sign in (-1, 1)
    )
    yield from offer(PREFERRED_LABEL_RADII, long_shifts)
    yield from offer(EXPANDED_LABEL_RADII, long_shifts)
'''
if old not in text:
    raise SystemExit("candidate-space target block not found; refusing to modify")
if text.count(old) != 1:
    raise SystemExit("candidate-space target block is not unique; refusing to modify")
PATH.write_text(text.replace(old, new), encoding="utf-8")
print(f"Expanded candidate space in {PATH}")
