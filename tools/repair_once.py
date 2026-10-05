#!/usr/bin/env python3
"""One-shot: avoid exhaustive routed MRV at the final alignment pair."""

from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

target = Path("tools/planet_finder_search_core.py")
source = target.read_text(encoding="utf-8")

old = '''        for _, candidate_item in geometry_ranked_items:
            check_deadline()
            probe_name = candidate_item[1][1]'''
new = '''        # At the final pair, exact routed MRV ranking can consume the whole
        # mode clock before DFS visits a node. Geometry ranking is a safe
        # ordering heuristic here; the recursive DFS still performs the full
        # authoritative routed viability checks for both members.
        final_pair_geometry_rank = len(remaining_items) == 2

        for _, candidate_item in geometry_ranked_items:
            check_deadline()
            probe_name = candidate_item[1][1]'''

old2 = '''            routed_rank = True
            cached_rows = None'''
new2 = '''            routed_rank = not final_pair_geometry_rank
            cached_rows = None'''

if source.count(old) != 1:
    raise SystemExit(f"Safety stop: final-pair loop anchor count={source.count(old)}")
if source.count(old2) != 1:
    raise SystemExit(f"Safety stop: routed-rank anchor count={source.count(old2)}")

source = source.replace(old, new).replace(old2, new2)
target.write_text(source, encoding="utf-8")

me = Path(__file__)
self_source = me.read_text(encoding="utf-8")
arming_line = "ENABLED" + " = True"
lines = self_source.splitlines()
matches = [i for i, line in enumerate(lines) if line.strip() == arming_line]
if len(matches) != 1:
    raise SystemExit(f"Safety stop: arming line count={len(matches)}")
lines[matches[0]] = "ENABLED = False"
me.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("Final pair now uses geometry for MRV ordering; Repair Once is OFF.")
