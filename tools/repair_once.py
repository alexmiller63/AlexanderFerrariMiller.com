from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()
start_marker = "    # Deterministic conjunction pre-pass. Each group is an atomic unit:\n"
end_marker = "    # Second phase: solve the entire alignment layer recursively."
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("Safety stop: conjunction pre-pass markers not found exactly once")
if text.find(start_marker, start + 1) >= 0 or text.find(end_marker, end + 1) >= 0:
    raise SystemExit("Safety stop: conjunction pre-pass markers are not unique")

new = '''    # Deterministic conjunction pre-pass.  Conjunction classification fixes
    # exact lambda and radial glyph slots, but it must not freeze an arbitrary
    # label arrangement.  Solve every conjunction as one atomic constraint
    # group, validate the complete group, and only then freeze it.
    by_name = {name: (i, (symbol, name, longitude)) for i, (symbol, name, longitude) in enumerate(bodies)}
    glyph_radii = conjunction_glyph_radii(bodies)
    glyph_radius = 22.0

    def solve_conjunction_group(group, group_index):
        group_items = [by_name[item[1]] for item in group]

        # Exact lambda is observational data.  Only radius changes to separate
        # coincident glyphs; these positions are immutable during label search.
        glyph_centers = {}
        for _, (_, name, longitude) in group_items:
            center = xy(longitude, glyph_radii[name])
            if any(math.hypot(center[0] - other[0], center[1] - other[1]) < 2.0 * glyph_radius
                   for other in glyph_centers.values()):
                raise RuntimeError(
                    f"Planet Finder {mode}: conjunction glyph overlap in group {group_index + 1} at {name}"
                )
            glyph_centers[name] = center

        # Build bounded candidate pools near each body's natural label
        # position.  The group search is deliberately local and deterministic;
        # ordinary DFS never sees these bodies once a complete group is frozen.
        pools = {}
        for _, (_, name, longitude) in group_items:
            w, h = label_size(mode, name)
            natural = xy(longitude, PREFERRED_LABEL_RADII[0])
            rows = []
            for x, y, box in legal_candidate_positions(
                    longitude, w, h, reserved, displacement_scale):
                if any(boxes_overlap(box, old, LABEL_COLLISION_PADDING) for old in placed):
                    continue
                if any(segment_hits_box(path[i], path[i + 1], box, PLACED_LABEL_LEADER_CLEARANCE)
                       for path in leaders for i in range(len(path) - 1)):
                    continue
                rows.append((x, y, box))
                if len(rows) >= 80:
                    break
            rows.sort(key=lambda row: math.hypot(row[0] - natural[0], row[1] - natural[1]))
            if not rows:
                return None
            pools[name] = rows

        chosen = {}
        chosen_paths = {}
        ordered_names = [item[1][1] for item in group_items]

        def label_angle(row):
            x, y, _ = row
            return (math.degrees(math.atan2(CY - y, x - CX)) - 180.0) % 360.0

        def preserves_lambda_order():
            present = [name for name in ordered_names if name in chosen]
            if len(present) < 2:
                return True
            reference = group_items[0][1][2] - 90.0
            angles = [((label_angle(chosen[name]) - reference) % 360.0) for name in present]
            return all(a < b for a, b in zip(angles, angles[1:]))

        def assign(depth):
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
                if leader_hits_zodiac_rim(path_candidate) or leaders_too_close(
                        path_candidate, leaders + list(chosen_paths.values())):
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
                f"lambda={longitude % 360.0:.3f}deg radius={glyph_radii[name]:.1f}",
                flush=True,
            )

'''

path.write_text(text[:start] + new + text[end:])
print("Installed atomic conjunction label/leader solver; exact lambda and glyph freezing preserved.")
