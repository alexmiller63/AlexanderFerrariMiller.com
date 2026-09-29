#!/usr/bin/env python3
"""One-shot repair: make conjunctions use the alignment layer's coordinated planner."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

# 1. Generalize the existing alignment planner so the exact same coordinated
# geometry can plan either the ordinary alignment layer or one conjunction blob.
old = '''    def plan_alignment_layer():
        """Preplace the alignment as one ordered, route-compatible layer.

        A bounded constraint search starts with nearby labels, keeps each
        group's circular lambda order, and checks routes while adding labels.
        The recursive alignment search below remains the fallback if this
        preferred pool cannot supply a complete layer.
        """
        items = [item for group in alignment_group_items for item in group]
'''
new = '''    def plan_alignment_layer(groups=None):
        """Preplace groups as one ordered, route-compatible layer.

        This is the shared coordinated-placement algorithm for both ordinary
        close alignments and conjunction blobs. Crossing the conjunction
        threshold changes atomicity only; it does not change placement geometry.
        """
        groups = alignment_group_items if groups is None else groups
        items = [item for group in groups for item in group]
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: alignment planner header did not match exactly once")
text = text.replace(old, new, 1)

# Within the planner only, use its selected groups rather than the outer
# ordinary-alignment list.
planner_start = text.index("    def plan_alignment_layer(groups=None):\n")
planner_end = text.index("    def stage_alignment_preplacement", planner_start)
planner = text[planner_start:planner_end]
planner = planner.replace(
    "for group in alignment_group_items\n            for left, right in zip(group, group[1:])",
    "for group in groups\n            for left, right in zip(group, group[1:])",
)
planner = planner.replace(
    "group_names = [[item[1][1] for item in group] for group in alignment_group_items]",
    "group_names = [[item[1][1] for item in group] for group in groups]",
)
text = text[:planner_start] + planner + text[planner_end:]

# 2. Replace the conjunction-only sequential member DFS.  The blob is first
# planned by the SAME coordinated planner that handles the known-good 2-degree
# case, then staged as one transaction. If downstream fails, the entire blob is
# restored together.
start_marker = "    def solve_conjunction_group(group, group_index, downstream):\n"
end_marker = "    conjunction_group_list = conjunction_groups(bodies)\n"
if text.count(start_marker) != 1 or text.count(end_marker) != 1:
    raise SystemExit("Safety stop: conjunction solver markers are not unique")
start = text.index(start_marker)
end = text.index(end_marker, start)

replacement = '''    def solve_conjunction_group(group, group_index, downstream):
        """Place a conjunction with ordinary coordinated geometry, atomically."""
        group_items = [by_name[item[1]] for item in group]
        ordered_names = [item[1][1] for item in group_items]

        # Critical invariant: 1 degree uses the same coordinated placement
        # algorithm as the close ordinary alignment case. The threshold changes
        # only the recursion unit: this completed group is committed/backtracked
        # as one blob.
        preplacement = plan_alignment_layer([group_items])
        if not preplacement:
            diagnostic_print(
                f"Planet Finder {mode}: CONJUNCTION COORDINATED-GEOMETRY EXHAUSTED "
                f"group={group_index + 1} bodies={' > '.join(ordered_names)}",
                flush=True,
            )
            return False

        planned, paths = preplacement
        staged_indices = []
        for original_index, (symbol, name, longitude) in group_items:
            box = planned[name][2]
            path = paths[name]
            placed.append(box)
            leaders.append(path)
            leader_names.append(name)
            staged[original_index] = (symbol, name, longitude, box, path)
            staged_indices.append(original_index)

        diagnostic_print(
            f"Planet Finder {mode}: CONJUNCTION BLOB COORDINATED-GEOMETRY "
            f"group={group_index + 1} bodies={' > '.join(ordered_names)}",
            flush=True,
        )

        try:
            if downstream():
                return True
        finally:
            # A solved layout deliberately keeps staged geometry for collection.
            # Restore only when downstream did not complete the whole search.
            if len(staged) < len(bodies):
                for original_index in staged_indices:
                    staged.pop(original_index, None)
                del leader_names[-len(group_items):]
                del leaders[-len(group_items):]
                del placed[-len(group_items):]
        return False

'''
text = text[:start] + replacement + text[end:]

TARGET.write_text(text, encoding="utf-8")

# Self-disarm after successful rewrite.
me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Conjunctions now use the same coordinated placement planner as close "
    "ordinary alignments, while remaining atomic for downstream backtracking. "
    "Repair Once is now OFF."
)
