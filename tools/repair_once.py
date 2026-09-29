#!/usr/bin/env python3
"""One-shot repair: make a 2-body conjunction start with the globally widest pair."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old = '''            _, (_, name, longitude) = group_items[depth]
            anchor = anchors[name]
            candidate_rows = pools[name]
            if chosen:
                # Once a sibling is chosen, try the remaining label positions
                # in maximum-separation-first order. Recursive failure then
                # moves inward only after wider alternatives have been tested.
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
new = '''            _, (_, name, longitude) = group_items[depth]
            anchor = anchors[name]
            candidate_rows = pools[name]
            if depth == 0 and len(group_items) == 2:
                # A conjunction is a pair-placement problem.  Do not freeze
                # body 1 merely because its own candidate is far from its
                # natural position.  Order body 1 by the widest pair it can
                # form with body 2.  The recursive sibling ordering below then
                # makes the very first attempted pair the GLOBAL widest pair.
                # This is deliberately limited to the current 2-body handler;
                # all legality, lambda-order, routing, caps, clocks, and
                # downstream backtracking remain unchanged.
                sibling_name = group_items[1][1][1]
                sibling_rows = pools[sibling_name]
                candidate_rows = sorted(
                    candidate_rows,
                    key=lambda row: max(
                        math.hypot(row[0] - sibling[0], row[1] - sibling[1])
                        for sibling in sibling_rows
                    ),
                    reverse=True,
                )
            if chosen:
                # Once a sibling is chosen, try the remaining label positions
                # in maximum-separation-first order. Recursive failure then
                # moves inward only after wider alternatives have been tested.
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

if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: conjunction candidate-order block count={text.count(old)}; expected 1"
    )

text = text.replace(old, new, 1)
TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Changed 2-body conjunction ordering so the first attempted pair is the "
    "globally widest available pair; preserved all existing geometry gates, "
    "lambda ordering, routing, budgets, clocks, and downstream backtracking; "
    "Repair Once is now OFF."
)
