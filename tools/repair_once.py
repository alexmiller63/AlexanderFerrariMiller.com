from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''    # Second deterministic phase: solve each broad alignment against immutable
    # geometry and all already-frozen conjunction/alignment placements.  Unlike
    # conjunctions, alignment siblings use ordinary label/leader collision
    # rules.  A small local DFS solves the entire group before it is frozen;
    # failure backtracks only within the group, never into a conjunction.
    for group_index, group in enumerate(alignment_groups(bodies)):
        group_items = [by_name[item[1]] for item in group]

        def place_alignment_member(member_index):
            if member_index == len(group_items):
                return True
            item = group_items[member_index]
            original_index, (symbol, name, longitude) = item
            # Negative diagnostic depths keep this pre-pass visibly distinct
            # from the ordinary recursive body's 0..N search depths.
            diagnostic_depth = -(group_index + 1)
            for box, path in viable_candidates(
                item, diagnostic_depth, consume_body_budget=False
            ):
                placed.append(box)
                leaders.append(path)
                leader_names.append(name)
                staged[original_index] = (symbol, name, longitude, box, path)
                if place_alignment_member(member_index + 1):
                    return True
                staged.pop(original_index, None)
                leader_names.pop()
                leaders.pop()
                placed.pop()
            return False

        if not place_alignment_member(0):
            names = " > ".join(item[1][1] for item in group_items)
            raise RuntimeError(
                f"Planet Finder {mode}: unable to place alignment group "
                f"{group_index + 1}: {names}"
            )
        diagnostic_print(
            f"Planet Finder {mode}: FIXED ALIGNMENT PLACED group={group_index + 1} "
            + " > ".join(item[1][1] for item in group_items),
            flush=True,
        )

'''

new = '''    # Second phase: solve the entire alignment layer recursively.  There are
    # two levels of backtracking: members within a group, and groups within the
    # alignment layer.  Nothing in this layer is truly frozen until every
    # alignment group has a mutually compatible complete placement.
    alignment_group_items = [
        [by_name[item[1]] for item in group]
        for group in alignment_groups(bodies)
    ]

    def solve_alignment_members(group_index, remaining_items):
        if not remaining_items:
            return solve_alignment_group(group_index + 1)

        # Squeaky-wheel ordering inside the group: try the member with the
        # fewest currently viable placements first.  Cache its candidates so
        # counting them does not change geometry or consume body budgets.
        choices = []
        diagnostic_depth = -(group_index + 1)
        for item in remaining_items:
            candidates = list(viable_candidates(
                item, diagnostic_depth, consume_body_budget=False
            ))
            choices.append((len(candidates), item[1][1], item, candidates))
        choices.sort(key=lambda row: (row[0], row[1]))
        count, _, item, candidates = choices[0]
        if count == 0:
            return False

        original_index, (symbol, name, longitude) = item
        next_remaining = [other for other in remaining_items if other is not item]
        for box, path in candidates:
            placed.append(box)
            leaders.append(path)
            leader_names.append(name)
            staged[original_index] = (symbol, name, longitude, box, path)
            if solve_alignment_members(group_index, next_remaining):
                return True
            staged.pop(original_index, None)
            leader_names.pop()
            leaders.pop()
            placed.pop()
        return False

    def solve_alignment_group(group_index):
        if group_index == len(alignment_group_items):
            return True
        group_items = alignment_group_items[group_index]
        placed_mark = len(placed)
        leaders_mark = len(leaders)
        names_mark = len(leader_names)
        staged_before = set(staged)

        if solve_alignment_members(group_index, list(group_items)):
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT LAYER group={group_index + 1} compatible "
                + " > ".join(item[1][1] for item in group_items),
                flush=True,
            )
            return True

        # A later group can force reconsideration of every placement made by
        # this group.  Restore exactly the geometry/staging state that existed
        # when the group was entered before its caller tries another branch.
        del placed[placed_mark:]
        del leaders[leaders_mark:]
        del leader_names[names_mark:]
        for key in list(staged):
            if key not in staged_before:
                staged.pop(key, None)
        return False

    if alignment_group_items and not solve_alignment_group(0):
        names = " | ".join(
            " > ".join(item[1][1] for item in group_items)
            for group_items in alignment_group_items
        )
        raise RuntimeError(
            f"Planet Finder {mode}: unable to solve recursive alignment layer: {names}"
        )

    if alignment_group_items:
        diagnostic_print(
            f"Planet Finder {mode}: FIXED ALIGNMENT LAYER groups={len(alignment_group_items)}",
            flush=True,
        )

'''

if text.count(old) != 1:
    raise SystemExit(f"Safety stop: expected old alignment phase once; found {text.count(old)}")

path.write_text(text.replace(old, new, 1))
print("Replaced sequential alignment freezing with recursive group/member alignment layer.")
