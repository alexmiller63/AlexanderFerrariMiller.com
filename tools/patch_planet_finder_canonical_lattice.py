#!/usr/bin/env python3
"""Repair-once: make circular lambda order a conjunction construction constraint."""
from pathlib import Path

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old = '''            candidate_rows = pools[name]\n            if chosen:\n                # Once one sibling has been placed, explicitly maximize the\n                # separation between conjunction labels first.  Stable sorting\n                # preserves the outer-to-inner pool order for ties.  Recursive\n                # failure naturally walks toward progressively narrower blobs.\n                chosen_centers = [(row[0], row[1]) for row in chosen.values()]\n                candidate_rows = sorted(\n                    candidate_rows,\n                    key=lambda row: min(\n                        math.hypot(row[0] - cx, row[1] - cy)\n                        for cx, cy in chosen_centers\n                    ),\n                    reverse=True,\n                )\n'''

new = '''            candidate_rows = pools[name]\n            if chosen:\n                # Circular lambda order is a construction constraint, not a\n                # high-volume rejection gate.  The conjunction members arrive\n                # in authoritative circular lambda order, so discard sibling\n                # positions that would invert that order before optimizing\n                # their separation.  preserves_lambda_order() remains below as\n                # an invariant/backstop.\n                reference = group_items[0][1][2] - 90.0\n                previous_name = ordered_names[depth - 1]\n                previous_angle = (label_angle(chosen[previous_name]) - reference) % 360.0\n                candidate_rows = [\n                    row for row in candidate_rows\n                    if ((label_angle(row) - reference) % 360.0) >= previous_angle\n                ]\n\n                # Among only order-preserving positions, try the widest blob\n                # first.  Recursive failure naturally walks toward narrower\n                # legal blobs without spending search on known lambda inversions.\n                chosen_centers = [(row[0], row[1]) for row in chosen.values()]\n                candidate_rows = sorted(\n                    candidate_rows,\n                    key=lambda row: min(\n                        math.hypot(row[0] - cx, row[1] - cy)\n                        for cx, cy in chosen_centers\n                    ),\n                    reverse=True,\n                )\n'''

count = text.count(old)
if count != 1:
    raise SystemExit(
        f"Refusing repair: expected conjunction candidate enumeration exactly once, found {count}"
    )
TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Applied circular-lambda-first conjunction candidate enumeration.")
