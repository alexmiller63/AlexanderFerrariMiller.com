#!/usr/bin/env python3
"""One-shot repair: stop a conjunction sibling branch when its widest geometry fails."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old = '''            for row_index, row in enumerate(candidate_rows):
                conjunction_attempts_by_body[name] += 1
                x, y, box = row
                tracing_widest_pair = depth == 1 and row_index == 0 and not widest_pair_trace["reported"]
'''
new = '''            # candidate_rows is widest-first. For conjunction siblings, a
            # failure of the maximum-separation geometry means this outer blob
            # placement/orientation cannot support the conjunction. Narrower
            # sibling geometry cannot repair that geometric failure, so return
            # to the parent blob search instead of squeezing inward.
            if chosen:
                candidate_rows = candidate_rows[:1]
            for row_index, row in enumerate(candidate_rows):
                conjunction_attempts_by_body[name] += 1
                x, y, box = row
                tracing_widest_pair = depth == 1 and row_index == 0 and not widest_pair_trace["reported"]
'''

if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: conjunction candidate loop count={text.count(old)}; expected 1"
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
    "Conjunction sibling search now stops after the widest geometry fails and "
    "backtracks to the outer blob search; Repair Once is now OFF."
)
