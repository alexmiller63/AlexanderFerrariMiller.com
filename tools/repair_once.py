#!/usr/bin/env python3
"""One-shot repair: make widest conjunction pruning failure-specific."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old_slice = '''            # candidate_rows is widest-first. For conjunction siblings, a
            # failure of the maximum-separation geometry means this outer blob
            # placement/orientation cannot support the conjunction. Narrower
            # sibling geometry cannot repair that geometric failure, so return
            # to the parent blob search instead of squeezing inward.
            if chosen:
                candidate_rows = candidate_rows[:1]
            for row_index, row in enumerate(candidate_rows):
'''
new_slice = '''            # candidate_rows is widest-first. Do not prune merely because the
            # widest candidate fails: routing, lambda order, and leader geometry
            # can improve at a narrower sibling position. Only monotonic space
            # failures may prune the remaining narrower candidates.
            for row_index, row in enumerate(candidate_rows):
'''

old_overlap = '''                if any(boxes_overlap(box, other[2], LABEL_COLLISION_PADDING)
                       for other in chosen.values()):
                    report_widest_pair("label_overlap")
                    diagnostic_rejections["label_overlap"] += 1
                    conjunction_rejections_by_body[name]["label_overlap"] += 1
                    continue
'''
new_overlap = '''                if any(boxes_overlap(box, other[2], LABEL_COLLISION_PADDING)
                       for other in chosen.values()):
                    report_widest_pair("label_overlap")
                    diagnostic_rejections["label_overlap"] += 1
                    conjunction_rejections_by_body[name]["label_overlap"] += 1
                    # Rows are ordered maximum-separation first. If even the
                    # widest sibling labels overlap, every narrower candidate
                    # is geometrically no better for this parent placement.
                    if chosen and row_index == 0:
                        return False
                    continue
'''

if text.count(old_slice) != 1:
    raise SystemExit(f"Safety stop: widest-only block count={text.count(old_slice)}; expected 1")
if text.count(old_overlap) != 1:
    raise SystemExit(f"Safety stop: label-overlap gate count={text.count(old_overlap)}; expected 1")

text = text.replace(old_slice, new_slice, 1)
text = text.replace(old_overlap, new_overlap, 1)
TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Conjunction widest pruning is now failure-specific: widest label overlap "
    "backtracks, while lambda/routing/leader failures may try narrower rows; "
    "Repair Once is now OFF."
)
