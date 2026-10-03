#!/usr/bin/env python3
"""One-shot: make same-blob forward checking geometry-only."""

from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")

old = '''                for future_item in next_remaining:
                    witness_stream = alignment_profiled_candidates(
                        future_item, diagnostic_depth, "same-blob-forward"
                    )
                    try:
                        next(witness_stream)
                    except StopIteration:
                        alignment_forward_ok = False
                        future_name = future_item[1][1]
'''
new = '''                for future_item in next_remaining:
                    # Forward checking needs only a necessary-condition witness.
                    # Absence of a collision-free geometry proves this prefix
                    # dead; presence merely defers exact leader routing until
                    # that member is actually explored by DFS.
                    witness_stream = alignment_geometry_candidates(future_item)
                    try:
                        next(witness_stream)
                    except StopIteration:
                        alignment_forward_ok = False
                        future_name = future_item[1][1]
'''

if text.count(old) != 1:
    raise SystemExit("Safety stop: same-blob forward witness block missing or non-unique")
P.write_text(text.replace(old, new, 1), encoding="utf-8")

me = Path(__file__)
source = me.read_text(encoding="utf-8")
needle = "\nENABLED = True\n"
if source.count(needle) != 1:
    raise SystemExit("Safety stop: ENABLED assignment not unique")
me.write_text(source.replace(needle, "\nENABLED = False\n", 1), encoding="utf-8")
print("Installed geometry-only same-blob forward checking; Repair Once is OFF.")
