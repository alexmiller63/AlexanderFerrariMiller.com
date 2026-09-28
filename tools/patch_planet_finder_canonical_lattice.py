#!/usr/bin/env python3
"""Repair-once: add diagnostic-only Mercury candidate stream distribution accounting."""
from pathlib import Path

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old_init = '''    viable_geometry_seen = {}\n    solutions = []\n'''
new_init = '''    viable_geometry_seen = {}\n    # Diagnostic only: summarize how Mercury's admitted candidates traverse\n    # label-position space.  This does not filter, reorder, or score anything.\n    mercury_candidate_stream = []\n    solutions = []\n'''
if text.count(old_init) != 1:
    raise SystemExit(f"Safety stop: uniqueness init block count={text.count(old_init)}; expected 1")
text = text.replace(old_init, new_init, 1)

old_seen = '''            seen = viable_geometry_seen.setdefault(name, set())\n            seen.add(geometry_signature)\n\n            # This is the single cap point: only a fully viable candidate\n'''
new_seen = '''            seen = viable_geometry_seen.setdefault(name, set())\n            seen.add(geometry_signature)\n\n            if name == "Mercury" and consume_body_budget:\n                # Polar coordinates around the exact Mercury anchor expose\n                # whether enumeration explores broadly or marches through one\n                # sector/radius before reaching the rest of the lattice.\n                dx = box.x - anchor[0]\n                dy = box.y - anchor[1]\n                mercury_candidate_stream.append((\n                    math.hypot(dx, dy),\n                    math.degrees(math.atan2(dy, dx)) % 360.0,\n                    box.x,\n                    box.y,\n                ))\n\n            # This is the single cap point: only a fully viable candidate\n'''
if text.count(old_seen) != 1:
    raise SystemExit(f"Safety stop: uniqueness admission block count={text.count(old_seen)}; expected 1")
text = text.replace(old_seen, new_seen, 1)

old_cap = '''                    f"lineage={cap_lineage(depth)}",\n                    flush=True,\n                )\n                raise DepthNodeBudgetExhausted(depth, name)\n'''
new_cap = '''                    f"lineage={cap_lineage(depth)}",\n                    flush=True,\n                )\n                if name == "Mercury" and mercury_candidate_stream:\n                    # Use cumulative doubling bands so the output lines map\n                    # directly onto the W1 200/400/800/1600/3200 ladder.\n                    bounds = (200, 400, 800, 1600, 3200)\n                    start = 0\n                    for stop in bounds:\n                        if start >= len(mercury_candidate_stream):\n                            break\n                        band = mercury_candidate_stream[start:min(stop, len(mercury_candidate_stream))]\n                        radii = [row[0] for row in band]\n                        angles = [row[1] for row in band]\n                        xs = [row[2] for row in band]\n                        ys = [row[3] for row in band]\n                        sectors = [0] * 8\n                        for angle in angles:\n                            sectors[min(7, int(angle // 45.0))] += 1\n                        diagnostic_print(\n                            f"Planet Finder {mode}: MERCURY-CANDIDATE-BAND "\n                            f"range={start + 1}-{start + len(band)} "\n                            f"radius[min={min(radii):.1f},max={max(radii):.1f},mean={sum(radii)/len(radii):.1f}] "\n                            f"x[min={min(xs):.1f},max={max(xs):.1f}] "\n                            f"y[min={min(ys):.1f},max={max(ys):.1f}] "\n                            f"sectors45={','.join(str(value) for value in sectors)}",\n                            flush=True,\n                        )\n                        start = stop\n                raise DepthNodeBudgetExhausted(depth, name)\n'''
if text.count(old_cap) != 2:
    raise SystemExit(f"Safety stop: cap block count={text.count(old_cap)}; expected 2")
text = text.replace(old_cap, new_cap)

TARGET.write_text(text, encoding="utf-8")
print("Added diagnostic-only Mercury candidate stream distribution accounting.")
