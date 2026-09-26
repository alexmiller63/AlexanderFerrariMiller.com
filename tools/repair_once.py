from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

# Place each conjunction atomically: members may not reject one another through
# ordinary label/leader collision rules. Their glyphs must still be distinct.
# Once the whole group is placed, freeze its labels/leaders as collision
# geometry for the remaining recursive bodies.

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()
old = '''    # Deterministic conjunction pre-pass.  No recursion: each member is taken
    # in circular lambda order and receives the first legal placement against
    # immutable geometry plus previously frozen conjunction members.  After
    # this loop these boxes/leaders stay in the collision sets for all DFS.
    conjunction_items = []
    by_name = {name: (i, (symbol, name, longitude)) for i, (symbol, name, longitude) in enumerate(bodies)}
    for group in conjunction_groups(bodies):
        conjunction_items.extend(by_name[item[1]] for item in group)
    for fixed_depth, item in enumerate(conjunction_items):
        original_index, (symbol, name, longitude) = item
        try:
            box, path = next(viable_candidates(item, -(fixed_depth + 1), consume_body_budget=False))
        except StopIteration:
            raise RuntimeError(
                f"Planet Finder {mode}: deterministic conjunction placement failed for {name}"
            )
        placed.append(box)
        leaders.append(path)
        leader_names.append(name)
        staged[original_index] = (symbol, name, longitude, box, path)
        diagnostic_print(
            f"Planet Finder {mode}: FIXED CONJUNCTION PLACED body={name} "
            f"lambda={longitude % 360.0:.3f}deg radius={conjunction_glyph_radii(bodies)[name]:.1f}",
            flush=True,
        )
'''
new = '''    # Deterministic conjunction pre-pass. Each group is an atomic unit:
    # choose its member placements against immutable geometry and previously
    # frozen groups, but do not let siblings in the same conjunction reject
    # one another through ordinary label/leader collision rules. Glyph overlap
    # is checked explicitly from the shared radial/longitude geometry.
    by_name = {name: (i, (symbol, name, longitude)) for i, (symbol, name, longitude) in enumerate(bodies)}
    glyph_radii = conjunction_glyph_radii(bodies)
    glyph_radius = 22.0

    for group_index, group in enumerate(conjunction_groups(bodies)):
        group_items = [by_name[item[1]] for item in group]

        # The glyph layer is the hard intra-conjunction constraint. Exact
        # lambda is preserved; radial slots must keep glyph circles disjoint.
        glyph_centers = []
        for _, (_, name, longitude) in group_items:
            center = xy(longitude, glyph_radii[name])
            if any(math.hypot(center[0] - other[0], center[1] - other[1]) < 2.0 * glyph_radius
                   for other in glyph_centers):
                raise RuntimeError(
                    f"Planet Finder {mode}: conjunction glyph overlap in group {group_index + 1} at {name}"
                )
            glyph_centers.append(center)

        # Snapshot only geometry frozen before this conjunction. Each sibling
        # is selected against that same snapshot, making the group atomic.
        base_placed_len = len(placed)
        base_leaders_len = len(leaders)
        group_rows = []
        for fixed_depth, item in enumerate(group_items):
            original_index, (symbol, name, longitude) = item
            del placed[base_placed_len:]
            del leaders[base_leaders_len:]
            del leader_names[base_leaders_len:]
            try:
                box, path = next(
                    viable_candidates(
                        item,
                        -(group_index * 100 + fixed_depth + 1),
                        consume_body_budget=False,
                    )
                )
            except StopIteration:
                raise RuntimeError(
                    f"Planet Finder {mode}: atomic conjunction placement failed for {name}"
                )
            group_rows.append((original_index, symbol, name, longitude, box, path))

        # Restore the frozen-before-group snapshot, then commit the complete
        # conjunction at once. From here on it is collision geometry only.
        del placed[base_placed_len:]
        del leaders[base_leaders_len:]
        del leader_names[base_leaders_len:]
        for original_index, symbol, name, longitude, box, path in group_rows:
            placed.append(box)
            leaders.append(path)
            leader_names.append(name)
            staged[original_index] = (symbol, name, longitude, box, path)
            diagnostic_print(
                f"Planet Finder {mode}: FIXED CONJUNCTION PLACED body={name} "
                f"lambda={longitude % 360.0:.3f}deg radius={glyph_radii[name]:.1f}",
                flush=True,
            )
'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: conjunction pre-pass count={text.count(old)}")
text = text.replace(old, new, 1)
path.write_text(text)

print("Conjunction groups now place atomically, forbid glyph overlap, then freeze as collisions.")
