from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

start_marker = "        ALIGNMENT_PROBE_LIMIT = 5\n"
end_marker = "            batch_start += len(batch)\n"
start = text.find(start_marker)
if start < 0:
    raise SystemExit("Safety stop: alignment probe block start not found")
end = text.find(end_marker, start)
if end < 0:
    raise SystemExit("Safety stop: alignment batch block end not found")
end += len(end_marker)
if text.find(start_marker, start + 1) >= 0:
    raise SystemExit("Safety stop: alignment probe block is not unique")

new = '''        # Build one bounded candidate set for each remaining member at this
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

path.write_text(text[:start] + new + text[end:])
print("Alignment controller now materializes each bounded candidate stream once per DFS prefix.")
