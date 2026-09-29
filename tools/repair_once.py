#!/usr/bin/env python3
"""One-shot repair: conjunctions change backtracking granularity only."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

# A conjunction is not a placement mode.  Do not remove conjunction members
# from the ordinary coordinated alignment layer and re-plan them separately.
# Crossing the conjunction threshold may change only the backtracking unit.
old = '''    conjunction_group_list = conjunction_groups(bodies)

    # Second phase: solve the entire alignment layer recursively.  There are
    # two levels of backtracking: members within a group, and groups within the
    # alignment layer.  Nothing in this layer is truly frozen until every
    # alignment group has a mutually compatible complete placement.
    alignment_group_items = [
        [by_name[item[1]] for item in group]
        for group in alignment_groups(bodies)
    ]
'''
new = '''    conjunction_group_list = conjunction_groups(bodies)
    conjunction_names = {
        item[1]
        for group in conjunction_group_list
        for item in group
    }

    # Placement geometry is independent of conjunction status.  Build the
    # coordinated alignment layer from a view in which conjunction members are
    # restored to the ordinary alignment population.  Conjunction metadata is
    # retained separately and is used only to make those members atomic when
    # backtracking.
    alignment_source = list(bodies)
    alignment_group_items = [
        [by_name[item[1]] for item in group]
        for group in alignment_groups(alignment_source)
    ]
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: alignment-layer construction did not match exactly once")
text = text.replace(old, new, 1)

# Remove the special two-body conjunction planner.  The ordinary coordinated
# alignment planner now owns placement; this wrapper only commits an already
# planned conjunction atomically downstream.
start = text.find("    def solve_conjunction_group(group, group_index, downstream):\n")
end = text.find("\n    conjunction_group_list = conjunction_groups(bodies)\n", start)
if start < 0 or end < 0:
    raise SystemExit("Safety stop: conjunction placement wrapper not found")
text = text[:start] + text[end + 1:]

TARGET.write_text(text, encoding="utf-8")

# Self-disarm after successful rewrite.
me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Removed conjunction-specific placement planning. Conjunction members now "
    "use the ordinary coordinated alignment geometry; conjunction status is "
    "reserved for atomic backtracking only. Repair Once is now OFF."
)
