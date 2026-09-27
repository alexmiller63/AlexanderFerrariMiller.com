#!/usr/bin/env python3
"""Repair-once patch: make conjunction blobs backtrack through downstream search.

A conjunction remains atomic internally, but its first locally valid layout is
no longer frozen permanently.  Complete blobs are staged as one outer-search
candidate; if alignment/ordinary DFS cannot finish beneath that blob, its whole
state is restored and the conjunction solver tries the next blob.

No geometry, routing, collision, candidate-pool, or budget rule is changed.
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
'''    def solve_conjunction_group(group, group_index):
''',
'''    def solve_conjunction_group(group, group_index, downstream):
''',
"conjunction solver signature",
)

replace_once(
'''        def assign(depth):
            if depth == len(group_items):
                return True
''',
'''        def assign(depth):
            if depth == len(group_items):
                # A complete conjunction is one atomic outer-search candidate.
                # Stage the whole blob, search everything beneath it, and if
                # downstream fails restore the entire blob before trying the
                # next internally valid conjunction arrangement.
                placed_mark = len(placed)
                leaders_mark = len(leaders)
                names_mark = len(leader_names)
                staged_before = set(staged)
                for original_index, (symbol, name, longitude) in group_items:
                    box = chosen[name][2]
                    leader = chosen_paths[name]
                    placed.append(box)
                    leaders.append(leader)
                    leader_names.append(name)
                    staged[original_index] = (symbol, name, longitude, box, leader)
                if downstream():
                    diagnostic_print(
                        f"Planet Finder {mode}: CONJUNCTION BLOB COMPATIBLE "
                        f"group={group_index + 1} bodies={' > '.join(ordered_names)}",
                        flush=True,
                    )
                    return True
                del placed[placed_mark:]
                del leaders[leaders_mark:]
                del leader_names[names_mark:]
                for key in list(staged):
                    if key not in staged_before:
                        staged.pop(key, None)
                return False
''',
"conjunction terminal staging",
)

replace_once(
'''        if not assign(0):
''',
'''        if not assign(0):
''',
"conjunction assignment guard",
)

replace_once(
'''            return None
        return [
            (original_index, symbol, name, longitude, chosen[name][2], chosen_paths[name])
            for original_index, (symbol, name, longitude) in group_items
        ]

    for group_index, group in enumerate(conjunction_groups(bodies)):
        solved = solve_conjunction_group(group, group_index)
        if solved is None:
            names = " > ".join(item[1] for item in group)
            raise RuntimeError(
                f"Planet Finder {mode}: no atomic conjunction layout for group {group_index + 1}: {names}"
            )
        # Freeze only a complete, mutually valid conjunction solution.
        for original_index, symbol, name, longitude, box, leader in solved:
            placed.append(box)
            leaders.append(leader)
            leader_names.append(name)
            staged[original_index] = (symbol, name, longitude, box, leader)
            diagnostic_print(
                f"Planet Finder {mode}: SOLVED CONJUNCTION FROZEN body={name} "
                f"lambda={longitude % 360.0:.3f}deg anchor_radius={RI - 5:.1f}",
                flush=True,
            )

    # Second phase: solve the entire alignment layer recursively.  There are
''',
'''            return False
        return True

    conjunction_group_list = conjunction_groups(bodies)

    # Second phase: solve the entire alignment layer recursively.  There are
''',
"frozen conjunction outer loop",
)

replace_once(
'''    alignment_preplacement = plan_alignment_layer()
    if alignment_preplacement:
        planned, paths = alignment_preplacement
        for group in alignment_group_items:
            for original_index, (symbol, name, longitude) in group:
                box = planned[name][2]
                path = paths[name]
                placed.append(box)
                leaders.append(path)
                leader_names.append(name)
                staged[original_index] = (symbol, name, longitude, box, path)

''',
'''    def stage_alignment_preplacement(alignment_preplacement):
        if not alignment_preplacement:
            return
        planned, paths = alignment_preplacement
        for group in alignment_group_items:
            for original_index, (symbol, name, longitude) in group:
                box = planned[name][2]
                path = paths[name]
                placed.append(box)
                leaders.append(path)
                leader_names.append(name)
                staged[original_index] = (symbol, name, longitude, box, path)

''',
"eager alignment preplacement",
)

replace_once(
'''    try:
        solved = _search_alignment_fallback(
            alignment_preplacement, alignment_group_items, placed, leaders,
            leader_names, staged, search, solve_alignment_group,
        )
        exhausted = not solved
''',
'''    def search_below_conjunctions():
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
''',
"top-level alignment invocation",
)

TARGET.write_text(text, encoding="utf-8")
print("Conjunction blobs are now backtrackable outer-search candidates.")
