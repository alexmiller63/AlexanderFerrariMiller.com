from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''        original_index, (symbol, name, longitude) = item
        next_remaining = [other for other in remaining_items if other is not item]
        # Now search the selected member's full viable stream.  The bounded
        # probe above affects ordering only; it never removes legal placements.
        for box, path in viable_candidates(
            item, diagnostic_depth, consume_body_budget=False
        ):
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

new = '''        original_index, (symbol, name, longitude) = item
        next_remaining = [other for other in remaining_items if other is not item]

        # Never suspend a live candidate generator across child recursion.  A
        # suspended generator's refinement clock includes all time spent in its
        # descendants, so the parent can falsely hit its deadline while doing
        # no candidate work.  Materialize a bounded batch, close the generator,
        # then recurse over ordinary data.  If the batch fails, request the next
        # batch from a fresh stream and skip the already-considered prefix.
        ALIGNMENT_BATCH_SIZE = 25
        batch_start = 0
        while True:
            batch = []
            candidate_stream = viable_candidates(
                item, diagnostic_depth, consume_body_budget=False
            )
            try:
                for candidate_index, candidate in enumerate(candidate_stream):
                    if candidate_index < batch_start:
                        continue
                    batch.append(candidate)
                    if len(batch) >= ALIGNMENT_BATCH_SIZE:
                        break
            finally:
                candidate_stream.close()

            if not batch:
                return False

            for box, path in batch:
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

            if len(batch) < ALIGNMENT_BATCH_SIZE:
                return False
            batch_start += len(batch)
'''

if text.count(old) != 1:
    raise SystemExit(f"Safety stop: expected live alignment candidate loop once; found {text.count(old)}")

path.write_text(text.replace(old, new, 1))
print("Alignment recursion now closes candidate generators before descending; candidates are searched in batches of 25.")
