from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''        # Squeaky-wheel ordering inside the group: try the member with the
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
'''

new = '''        # Squeaky-wheel ordering inside the group must be cheap.  Probe only a
        # small prefix of each member's viable stream; exhaustively enumerating
        # every candidate merely to choose the next body can consume the whole
        # mode clock before recursion does useful work.
        ALIGNMENT_PROBE_LIMIT = 5
        choices = []
        diagnostic_depth = -(group_index + 1)
        for item in remaining_items:
            probe = []
            candidate_stream = viable_candidates(
                item, diagnostic_depth, consume_body_budget=False
            )
            for candidate in candidate_stream:
                probe.append(candidate)
                if len(probe) >= ALIGNMENT_PROBE_LIMIT:
                    break
            choices.append((len(probe), item[1][1], item))
        choices.sort(key=lambda row: (row[0], row[1]))
        count, _, item = choices[0]
        if count == 0:
            return False

        original_index, (symbol, name, longitude) = item
        next_remaining = [other for other in remaining_items if other is not item]
        # Now search the selected member's full viable stream.  The bounded
        # probe above affects ordering only; it never removes legal placements.
        for box, path in viable_candidates(
            item, diagnostic_depth, consume_body_budget=False
        ):
'''

if text.count(old) != 1:
    raise SystemExit(f"Safety stop: expected exhaustive alignment heuristic once; found {text.count(old)}")

path.write_text(text.replace(old, new, 1))
print("Bounded alignment squeaky-wheel probes at 5 candidates; full search remains unchanged.")
