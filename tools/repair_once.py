#!/usr/bin/env python3
"""One-shot: remove redundant final-pair alignment support probing."""

from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

target = Path("tools/planet_finder_search_core.py")
source = target.read_text(encoding="utf-8")

old = '''        if next_remaining and not chosen_capped and chosen_count <= support_limit:
            support_stream = alignment_profiled_candidates(
                item, diagnostic_depth, "alignment-support"
            )'''
new = '''        # Do not pre-prove support when exactly one alignment member remains.
        # The recursive member DFS immediately performs that same authoritative
        # routed search. W17 showed this duplicate final-pair proof being paid
        # hundreds of times (especially Moon/Uranus) without opening new geometry.
        if len(next_remaining) > 1 and not chosen_capped and chosen_count <= support_limit:
            support_stream = alignment_profiled_candidates(
                item, diagnostic_depth, "alignment-support"
            )'''

if source.count(old) != 1:
    raise SystemExit(f"Safety stop: expected exactly one support-gate match, found {source.count(old)}")

source = source.replace(old, new)
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

print("Removed redundant final-pair support probe; Repair Once is OFF.")
