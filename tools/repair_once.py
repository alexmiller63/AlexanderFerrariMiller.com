from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

search_path = Path("tools/planet_finder_search.py")
core_path = Path("tools/planet_finder_search_core.py")
search = search_path.read_text()
core = core_path.read_text()

old_search_import = '''    legal_candidate_positions, route, conjunction_groups,
'''
new_search_import = '''    legal_candidate_positions, route, alignment_groups, conjunction_groups,
'''
if search.count(old_search_import) != 1:
    raise SystemExit(f"Safety stop: search import count={search.count(old_search_import)}")
search = search.replace(old_search_import, new_search_import, 1)

old_search_phase = '''    indexed = [item for item in indexed if item[1][1] not in conjunction_names]
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
'''
new_search_phase = '''    indexed = [item for item in indexed if item[1][1] not in conjunction_names]
    if conjunction_names:
        diagnostic_print(
            f"Planet Finder {mode}: FIXED CONJUNCTIONS "
            + " > ".join(
                item[1]
                for group in conjunction_groups(bodies)
                for item in group
            )
            + "; remaining after conjunctions=" + str(len(indexed)),
            flush=True,
        )

    # Broad alignments are the second placement phase.  Their members are
    # solved and frozen inside _solve_order after conjunctions, so the general
    # squeaky-wheel controller must never promote or recursively reconsider them.
    alignment_names = {
        item[1]
        for group in alignment_groups(bodies)
        for item in group
    }
    indexed = [item for item in indexed if item[1][1] not in alignment_names]
    if alignment_names:
        diagnostic_print(
            f"Planet Finder {mode}: FIXED ALIGNMENTS "
            + " | ".join(
                " > ".join(item[1] for item in group)
                for group in alignment_groups(bodies)
            )
            + "; recursive bodies=" + str(len(indexed)),
            flush=True,
        )
'''
if search.count(old_search_phase) != 1:
    raise SystemExit(f"Safety stop: search phase block count={search.count(old_search_phase)}")
search = search.replace(old_search_phase, new_search_phase, 1)

old_core_import = '''    legal_candidate_positions, route, conjunction_groups, conjunction_glyph_radii,
'''
new_core_import = '''    legal_candidate_positions, route, alignment_groups, conjunction_groups, conjunction_glyph_radii,
'''
if core.count(old_core_import) != 1:
    raise SystemExit(f"Safety stop: core import count={core.count(old_core_import)}")
core = core.replace(old_core_import, new_core_import, 1)

anchor = '''    forward_stats = {"checks": 0, "pruned": 0, "witnesses": 0, "by_body": {}}
'''
alignment_phase = '''    # Second deterministic phase: solve each broad alignment against immutable
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

    forward_stats = {"checks": 0, "pruned": 0, "witnesses": 0, "by_body": {}}
'''
if core.count(anchor) != 1:
    raise SystemExit(f"Safety stop: alignment placement anchor count={core.count(anchor)}")
core = core.replace(anchor, alignment_phase, 1)

search_path.write_text(search)
core_path.write_text(core)
print("Added conjunction -> freeze -> alignment -> freeze -> general-search pipeline.")
