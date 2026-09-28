#!/usr/bin/env python3
"""One-shot diagnostic: restore sequential candidate ordering for 2-body conjunctions."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old_pool_sort = '''            rows.sort(
                key=lambda row: math.hypot(row[0] - natural[0], row[1] - natural[1]),
                reverse=True,
            )
'''
new_pool_sort = '''            # Diagnostic canary: for a 2-body conjunction only, retain the
            # original sequential legal_candidate_positions() order. Larger
            # conjunctions keep the current outside-in ordering unchanged.
            if len(group_items) != 2:
                rows.sort(
                    key=lambda row: math.hypot(row[0] - natural[0], row[1] - natural[1]),
                    reverse=True,
                )
'''

old_pair_sort = '''            if chosen:
                # Once one sibling has been placed, explicitly maximize the
                # separation between conjunction labels first.  Stable sorting
                # preserves the outer-to-inner pool order for ties.  Recursive
                # failure naturally walks toward progressively narrower blobs.
                chosen_centers = [(row[0], row[1]) for row in chosen.values()]
                candidate_rows = sorted(
                    candidate_rows,
                    key=lambda row: min(
                        math.hypot(row[0] - cx, row[1] - cy)
                        for cx, cy in chosen_centers
                    ),
                    reverse=True,
                )
'''
new_pair_sort = '''            if chosen and len(group_items) != 2:
                # Larger conjunctions keep the current widest-first sibling
                # ordering. The 2-body diagnostic canary deliberately keeps
                # the sequential pool order so we can isolate ordering itself.
                chosen_centers = [(row[0], row[1]) for row in chosen.values()]
                candidate_rows = sorted(
                    candidate_rows,
                    key=lambda row: min(
                        math.hypot(row[0] - cx, row[1] - cy)
                        for cx, cy in chosen_centers
                    ),
                    reverse=True,
                )
'''

if text.count(old_pool_sort) != 1:
    raise SystemExit(
        f"Safety stop: conjunction pool-sort block count={text.count(old_pool_sort)}; expected 1"
    )
if text.count(old_pair_sort) != 1:
    raise SystemExit(
        f"Safety stop: conjunction sibling-sort block count={text.count(old_pair_sort)}; expected 1"
    )

text = text.replace(old_pool_sort, new_pool_sort, 1)
text = text.replace(old_pair_sort, new_pair_sort, 1)
TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "2-body conjunction canary now uses sequential candidate ordering; "
    "larger conjunction ordering is unchanged; Repair Once is now OFF."
)
