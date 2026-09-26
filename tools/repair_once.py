from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''        # Squeaky-wheel ordering inside the group must be cheap.  Probe only a
        # small prefix of each member's viable stream; exhaustively enumerating
        # every candidate merely to choose the next body can consume the whole
        # mode clock before recursion does useful work.
        # Build one bounded candidate set for each remaining member at this
        # DFS prefix.  The old probe/batch controller repeatedly regenerated
        # the same stream, so tight alignments spent their clock replaying
        # prefixes instead of advancing recursion.
        alignment_candidate_limit = budget["max_node_candidates"]
        choices = []
        diagnostic_depth = -(group_index + 1)
        for item in remaining_items:
            materialized = []
            candidate_stream = viable_candidates(
                item, diagnostic_depth, consume_body_budget=False
            )
            try:
                for candidate in candidate_stream:
                    materialized.append(candidate)
                    if len(materialized) >= alignment_candidate_limit:
                        break
            finally:
                candidate_stream.close()
            choices.append((len(materialized), item[1][1], item, materialized))

        choices.sort(key=lambda row: (row[0], row[1]))
        count, _, item, materialized = choices[0]
        if count == 0:
            return False

        original_index, (symbol, name, longitude) = item
        next_remaining = [other for other in remaining_items if other is not item]

        # Recursion owns ordinary data, never a suspended generator.  Each
        # candidate is generated once for this prefix and tried once.
        for box, path in materialized:
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
'''

new = '''        # Probe a small prefix for squeaky-wheel ordering, then keep the chosen
        # body's generator alive while recursion consumes it incrementally.
        # Unlike the old batch controller, we never restart the generator or
        # replay an already-considered prefix.  Unlike full materialization, we
        # do not spend the mode clock enumerating thousands of unused choices.
        ALIGNMENT_PROBE_LIMIT = 5
        diagnostic_depth = -(group_index + 1)
        choices = []
        for item in remaining_items:
            candidate_stream = viable_candidates(
                item, diagnostic_depth, consume_body_budget=False
            )
            probe = []
            exhausted = False
            try:
                for _ in range(ALIGNMENT_PROBE_LIMIT):
                    try:
                        probe.append(next(candidate_stream))
                    except StopIteration:
                        exhausted = True
                        break
            except Exception:
                candidate_stream.close()
                raise
            choices.append((len(probe), item[1][1], item, probe, candidate_stream, exhausted))

        choices.sort(key=lambda row: (row[0], row[1]))
        count, _, item, probe, chosen_stream, exhausted = choices[0]
        for _, _, other_item, _, other_stream, _ in choices[1:]:
            other_stream.close()
        if count == 0:
            chosen_stream.close()
            return False

        original_index, (symbol, name, longitude) = item
        next_remaining = [other for other in remaining_items if other is not item]
        tried = 0
        candidate_limit = budget["max_node_candidates"]

        def try_candidate(candidate):
            box, path = candidate
            placed.append(box)
            leaders.append(path)
            leader_names.append(name)
            staged[original_index] = (symbol, name, longitude, box, path)
            solved = solve_alignment_members(group_index, next_remaining)
            staged.pop(original_index, None)
            leader_names.pop()
            leaders.pop()
            placed.pop()
            return solved

        try:
            for candidate in probe:
                tried += 1
                if try_candidate(candidate):
                    return True
            if not exhausted:
                for candidate in chosen_stream:
                    tried += 1
                    if try_candidate(candidate):
                        return True
                    if tried >= candidate_limit:
                        break
        finally:
            chosen_stream.close()
        return False
'''

if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: expected current alignment controller once; found {text.count(old)}"
    )

path.write_text(text.replace(old, new, 1))
print("Alignment recursion now consumes one candidate stream incrementally without replay.")
