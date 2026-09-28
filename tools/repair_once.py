#!/usr/bin/env python3
"""One-shot diagnostic: restore pre-lambda-filter conjunction behavior."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")
old = '''            if chosen:\n                # Circular lambda order is a construction constraint, not a\n                # high-volume rejection gate.  The conjunction members arrive\n                # in authoritative circular lambda order, so discard sibling\n                # positions that would invert that order before optimizing\n                # their separation.  preserves_lambda_order() remains below as\n                # an invariant/backstop.\n                reference = group_items[0][1][2] - 90.0\n                previous_name = ordered_names[depth - 1]\n                previous_angle = (label_angle(chosen[previous_name]) - reference) % 360.0\n                candidate_rows = [\n                    row for row in candidate_rows\n                    if ((label_angle(row) - reference) % 360.0) >= previous_angle\n                ]\n\n                # Among only order-preserving positions, try the widest blob\n                # first.  Recursive failure naturally walks toward narrower\n                # legal blobs without spending search on known lambda inversions.\n                chosen_centers = [(row[0], row[1]) for row in chosen.values()]\n'''
new = '''            if chosen:\n                # Once one sibling has been placed, explicitly maximize the\n                # separation between conjunction labels first.  Stable sorting\n                # preserves the outer-to-inner pool order for ties.  Recursive\n                # failure naturally walks toward progressively narrower blobs.\n                chosen_centers = [(row[0], row[1]) for row in chosen.values()]\n'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: lambda pre-filter block count={text.count(old)}; expected 1")
TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")
print("Restored pre-lambda-filter conjunction behavior for regression diagnostic; Repair Once is now OFF.")
