#!/usr/bin/env python3
"""One-shot repair: remove obsolete conjunction placement recursion."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old = '''    def search_below_conjunctions():
        # Alignment planning depends on the currently staged conjunction blob,
        # so rebuild it for every blob candidate rather than carrying geometry
        # from a failed conjunction branch into the next one.
        alignment_preplacement = plan_alignment_layer()
        stage_alignment_preplacement(alignment_preplacement)
        return _search_alignment_fallback(
            alignment_preplacement, alignment_group_items, placed, leaders,
            leader_names, staged, search, solve_alignment_group,
        )

    def solve_conjunction_layer(group_index):
        if group_index == len(conjunction_group_list):
            return search_below_conjunctions()
        group = conjunction_group_list[group_index]
        return solve_conjunction_group(
            group,
            group_index,
            lambda: solve_conjunction_layer(group_index + 1),
        )

    try:
        solved = solve_conjunction_layer(0)
        exhausted = not solved
'''
new = '''    def search_coordinated_geometry():
        # Conjunctions have no placement path of their own.  Every body enters
        # the ordinary coordinated alignment planner; conjunction metadata is
        # consulted only by downstream backtracking to keep a conjunction
        # atomic when it must be reconsidered.
        alignment_preplacement = plan_alignment_layer()
        stage_alignment_preplacement(alignment_preplacement)
        return _search_alignment_fallback(
            alignment_preplacement, alignment_group_items, placed, leaders,
            leader_names, staged, search, solve_alignment_group,
        )

    try:
        solved = search_coordinated_geometry()
        exhausted = not solved
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: obsolete conjunction recursion did not match exactly once")
text = text.replace(old, new, 1)

TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Removed the dangling conjunction-placement recursion. There is now one "
    "coordinated placement path; conjunction metadata remains only for atomic "
    "backtracking. Repair Once is now OFF."
)
