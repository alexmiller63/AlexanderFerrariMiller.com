#!/usr/bin/env python3
"""Repair-once patch: search conjunction label geometry wide-to-narrow.

For conjunction bodies, keep the real astronomical longitudes unchanged.
Change only the ordering of candidate label placements inside the conjunction
blob search: begin with labels maximally displaced from their natural positions,
and for each later sibling try positions farthest from already chosen sibling
labels first.  The existing collision, lambda-order, routing, rim, and leader
checks remain authoritative.  If a wide blob is invalid, recursion continues
inward through progressively narrower alternatives.

This is deliberately an ordering change, not a relaxation of geometry.
Refuse to write unless every exact target occurs once.
"""
from pathlib import Path

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"Refusing repair: expected {label} exactly once, found {count}"
        )
    text = text.replace(old, new, 1)


replace_once(
'''            rows.sort(key=lambda row: math.hypot(row[0] - natural[0], row[1] - natural[1]))
            rows = rows[:80]
''',
'''            # Conjunctions are hardest when their labels begin crowded near
            # nearly coincident anchors.  Search from the easy outside inward:
            # retain the same bounded pool, but try the most displaced label
            # positions first.  No candidate is made legal by this ordering.
            rows.sort(
                key=lambda row: math.hypot(row[0] - natural[0], row[1] - natural[1]),
                reverse=True,
            )
            rows = rows[:80]
''',
"conjunction pool ordering",
)

replace_once(
'''            _, (_, name, longitude) = group_items[depth]
            anchor = anchors[name]
            for row in pools[name]:
                conjunction_attempts_by_body[name] += 1
''',
'''            _, (_, name, longitude) = group_items[depth]
            anchor = anchors[name]
            candidate_rows = pools[name]
            if chosen:
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
            for row in candidate_rows:
                conjunction_attempts_by_body[name] += 1
''',
"conjunction sibling ordering",
)

TARGET.write_text(text, encoding="utf-8")
print("Conjunction blob search now tries maximum label separation first, then narrows.")
