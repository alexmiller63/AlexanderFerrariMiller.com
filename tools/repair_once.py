from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

# Conjunction members are placed deterministically first.  They are then
# frozen: the recursive solver sees their labels/leaders only as collisions.

# 1. Remove conjunction members from the recursive controller order.
path = Path("tools/planet_finder_search.py")
text = path.read_text()
old = '''    legal_candidate_positions, route,
)'''
new = '''    legal_candidate_positions, route, conjunction_groups,
)'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: search import point count={text.count(old)}")
text = text.replace(old, new, 1)
old = '''    indexed = lambda_sorted[seam_after + 1:] + lambda_sorted[:seam_after + 1]

    # Diagnostic: report the closest pair'''
new = '''    indexed = lambda_sorted[seam_after + 1:] + lambda_sorted[:seam_after + 1]

    # Near-conjunction members are resolved deterministically before DFS.
    # They remain in `bodies` and therefore in the final rendered result, but
    # are absent from the squeaky-wheel order: once placed, they are collisions
    # only and can never be promoted or recursively reconsidered.
    conjunction_names = {
        item[1]
        for group in conjunction_groups(bodies)
        for item in group
    }
    indexed = [item for item in indexed if item[1][1] not in conjunction_names]
    if conjunction_names:
        diagnostic_print(
            f"Planet Finder {mode}: FIXED CONJUNCTIONS "
            + " > ".join(
                item[1]
                for group in conjunction_groups(bodies)
                for item in group
            )
            + "; recursive bodies=" + str(len(indexed)),
            flush=True,
        )

    # Diagnostic: report the closest pair'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: search order point count={text.count(old)}")
text = text.replace(old, new, 1)
path.write_text(text)

# 2. Pre-place conjunction labels/leaders in lambda order, using their shared
# displaced glyph radii as leader anchors.  Then leave them in placed/leaders.
path = Path("tools/planet_finder_search_core.py")
text = path.read_text()
old = '''    legal_candidate_positions, route,
)'''
new = '''    legal_candidate_positions, route, conjunction_groups, conjunction_glyph_radii,
)'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: core import point count={text.count(old)}")
text = text.replace(old, new, 1)
old = '''        anchor = xy(longitude, RI - 5)
        # This generator is created for one fixed DFS prefix.'''
new = '''        glyph_radii = conjunction_glyph_radii(bodies)
        anchor = xy(longitude, glyph_radii.get(name, RI - 5))
        # This generator is created for one fixed DFS prefix.'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: candidate anchor count={text.count(old)}")
text = text.replace(old, new, 1)

marker = '''    forward_stats = {"checks": 0, "pruned": 0, "witnesses": 0, "by_body": {}}
'''
addition = '''    # Deterministic conjunction pre-pass.  No recursion: each member is taken
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
if text.count(marker) != 1:
    raise SystemExit(f"Safety stop: forward marker count={text.count(marker)}")
text = text.replace(marker, addition + marker, 1)
path.write_text(text)

print("Conjunction members now pre-place once and remain collision-only during DFS.")
