from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old_assign = '''        def assign(depth):
            if depth == len(group_items):
                return True
            _, (_, name, longitude) = group_items[depth]
            anchor = glyph_centers[name]
            for row in pools[name]:
                x, y, box = row
                if any(boxes_overlap(box, other[2], LABEL_COLLISION_PADDING)
                       for other in chosen.values()):
                    continue
                chosen[name] = row
                if not preserves_lambda_order():
                    chosen.pop(name, None)
                    continue
                other_boxes = [other[2] for other_name, other in chosen.items() if other_name != name]
                path_candidate = route(
                    anchor, (x, y), reserved + placed + other_boxes,
                    allow_initial_escape_count=3,
                )
                if path_candidate is None:
                    chosen.pop(name, None)
                    continue
                if any(segment_hits_box(path_candidate[i], path_candidate[i + 1], other_box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for other_box in other_boxes for i in range(len(path_candidate) - 1)):
                    chosen.pop(name, None)
                    continue
                # Conjunction siblings intentionally originate at nearly the
                # same lambda, so their leaders may be close near the anchors.
                # Keep the ordinary clearance rule against leaders outside this
                # atomic conjunction, while sibling leader/label collisions are
                # checked explicitly above and below.
                if leader_hits_zodiac_rim(path_candidate) or leaders_too_close(
                        path_candidate, leaders):
                    chosen.pop(name, None)
                    continue
                # Symmetric collision check: an already chosen sibling leader
                # may not pass through this newly chosen label.
                if any(segment_hits_box(old_path[i], old_path[i + 1], box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for old_path in chosen_paths.values() for i in range(len(old_path) - 1)):
                    chosen.pop(name, None)
                    continue
                chosen_paths[name] = path_candidate
                if assign(depth + 1):
                    return True
                chosen_paths.pop(name, None)
                chosen.pop(name, None)
            return False

        if not assign(0):
            return None
        return [
            (original_index, symbol, name, longitude, chosen[name][2], chosen_paths[name])
            for original_index, (symbol, name, longitude) in group_items
        ]
'''
new_assign = '''        def assign(depth):
            if depth == len(group_items):
                yield [
                    (original_index, symbol, name, longitude,
                     chosen[name][2], chosen_paths[name])
                    for original_index, (symbol, name, longitude) in group_items
                ]
                return
            _, (_, name, longitude) = group_items[depth]
            anchor = glyph_centers[name]
            for row in pools[name]:
                x, y, box = row
                if any(boxes_overlap(box, other[2], LABEL_COLLISION_PADDING)
                       for other in chosen.values()):
                    continue
                chosen[name] = row
                if not preserves_lambda_order():
                    chosen.pop(name, None)
                    continue
                other_boxes = [other[2] for other_name, other in chosen.items() if other_name != name]
                path_candidate = route(
                    anchor, (x, y), reserved + placed + other_boxes,
                    allow_initial_escape_count=3,
                )
                if path_candidate is None:
                    chosen.pop(name, None)
                    continue
                if any(segment_hits_box(path_candidate[i], path_candidate[i + 1], other_box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for other_box in other_boxes for i in range(len(path_candidate) - 1)):
                    chosen.pop(name, None)
                    continue
                if leader_hits_zodiac_rim(path_candidate) or leaders_too_close(
                        path_candidate, leaders):
                    chosen.pop(name, None)
                    continue
                if any(segment_hits_box(old_path[i], old_path[i + 1], box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for old_path in chosen_paths.values() for i in range(len(old_path) - 1)):
                    chosen.pop(name, None)
                    continue
                chosen_paths[name] = path_candidate
                yield from assign(depth + 1)
                chosen_paths.pop(name, None)
                chosen.pop(name, None)

        yield from assign(0)
'''

old_freeze = '''    for group_index, group in enumerate(conjunction_groups(bodies)):
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
                f"lambda={longitude % 360.0:.3f}deg radius={glyph_radii[name]:.1f}",
                flush=True,
            )

    # Second phase: solve the entire alignment layer recursively.  There are
'''
new_freeze = '''    conjunction_group_items = list(enumerate(conjunction_groups(bodies)))

    # Conjunction groups are atomic choices, not permanent preplacements.
    # The actual downstream search entry is supplied later, after search() and
    # the alignment fallback helper are available.

    # Second phase: solve the entire alignment layer recursively.  There are
'''

old_entry = '''    try:
        solved = _search_alignment_fallback(
            alignment_preplacement, alignment_group_items, placed, leaders,
            leader_names, staged, search, solve_alignment_group,
        )
        exhausted = not solved
'''
new_entry = '''    def search_after_conjunctions():
        return _search_alignment_fallback(
            alignment_preplacement, alignment_group_items, placed, leaders,
            leader_names, staged, search, solve_alignment_group,
        )

    def solve_conjunction_layer(group_position):
        if group_position == len(conjunction_group_items):
            return search_after_conjunctions()

        group_index, group = conjunction_group_items[group_position]
        found_candidate = False
        for solved_group in solve_conjunction_group(group, group_index):
            found_candidate = True
            placed_mark = len(placed)
            leaders_mark = len(leaders)
            names_mark = len(leader_names)
            staged_before = set(staged)
            for original_index, symbol, name, longitude, box, leader in solved_group:
                placed.append(box)
                leaders.append(leader)
                leader_names.append(name)
                staged[original_index] = (symbol, name, longitude, box, leader)
            if solve_conjunction_layer(group_position + 1):
                return True
            del placed[placed_mark:]
            del leaders[leaders_mark:]
            del leader_names[names_mark:]
            for key in list(staged):
                if key not in staged_before:
                    staged.pop(key, None)

        if not found_candidate:
            names = " > ".join(item[1] for item in group)
            diagnostic_print(
                f"Planet Finder {mode}: no atomic conjunction candidate for "
                f"group {group_index + 1}: {names}", flush=True
            )
        return False

    try:
        solved = solve_conjunction_layer(0)
        exhausted = not solved
'''

for label, old in (("conjunction assign", old_assign),
                   ("frozen conjunction loop", old_freeze),
                   ("actual downstream search entry", old_entry)):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Safety stop: expected {label} exactly once; found {count}")

text = text.replace(old_assign, new_assign, 1)
text = text.replace(old_freeze, new_freeze, 1)
text = text.replace(old_entry, new_entry, 1)
path.write_text(text)
print("Conjunction layouts are now atomic backtrackable choices around the real downstream search entry.")
