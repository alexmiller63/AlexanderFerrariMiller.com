from pathlib import Path

PATH = Path("tools/planet_finder_search_core.py")
text = PATH.read_text()

old_helper = '''    def solve_final_body(last_depth):
        """Solve the final body directly against the placed penultimate body.

        The ordinary per-body cap is deliberately not charged here. At this
        point the task is a bounded compatibility join between the final two
        bodies, not a new ordering search. This avoids repeatedly exhausting
        Sun/Venus-style endgames after the first nine bodies are already fixed.
        """
        nonlocal candidates, backtracks, current_body
        item = order[last_depth]
        original_index, (symbol, name, longitude) = item
        current_body = name
        diagnostic_print(
            f"Planet Finder {mode}: TWO-BODY ENDGAME penultimate={order[last_depth - 1][1][1]} "
            f"final={name} depth={last_depth}/{len(order)}",
            level=2,
            flush=True,
        )

        for box, path in viable_candidates(item, last_depth, consume_body_budget=False):
            candidates += 1
            placed.append(box)
            leaders.append(path)
            leader_names.append(name)
            staged[original_index] = (symbol, name, longitude, box, path)
            try:
                if search(len(order)):
                    return True
            finally:
                staged.pop(original_index, None)
                leaders.pop()
                leader_names.pop()
                placed.pop()
            backtracks += 1
        return False
'''

new_helper = '''    def solve_final_pair(first_depth):
        """Solve the final two bodies as one bounded compatibility join.

        Neither member of the pair consumes the ordinary per-body DFS budget.
        The pair has its own bounded viable-pair budget so Sun/Venus-style
        endgames can be explored together without turning into an unbounded
        nested search.
        """
        nonlocal candidates, backtracks, current_body
        first_item = order[first_depth]
        second_item = order[first_depth + 1]
        first_index, (first_symbol, first_name, first_longitude) = first_item
        second_index, (second_symbol, second_name, second_longitude) = second_item
        pair_cap = max(1, int(os.environ.get("PLANET_FINDER_ENDGAME_PAIR_CAP", "2000")))
        pair_attempts = 0
        current_body = first_name
        diagnostic_print(
            f"Planet Finder {mode}: TWO-BODY ENDGAME pair={first_name}+{second_name} "
            f"depth={first_depth}/{len(order)} cap={pair_cap}",
            level=1,
            flush=True,
        )

        for first_box, first_path in viable_candidates(
            first_item, first_depth, consume_body_budget=False
        ):
            candidates += 1
            placed.append(first_box)
            leaders.append(first_path)
            leader_names.append(first_name)
            staged[first_index] = (
                first_symbol, first_name, first_longitude, first_box, first_path
            )
            try:
                current_body = second_name
                for second_box, second_path in viable_candidates(
                    second_item, first_depth + 1, consume_body_budget=False
                ):
                    pair_attempts += 1
                    if pair_attempts > pair_cap:
                        diagnostic_print(
                            f"Planet Finder {mode}: TWO-BODY ENDGAME CAP "
                            f"pair={first_name}+{second_name} attempts={pair_cap}",
                            level=1,
                            flush=True,
                        )
                        return False
                    candidates += 1
                    placed.append(second_box)
                    leaders.append(second_path)
                    leader_names.append(second_name)
                    staged[second_index] = (
                        second_symbol, second_name, second_longitude,
                        second_box, second_path,
                    )
                    try:
                        if search(len(order)):
                            return True
                    finally:
                        staged.pop(second_index, None)
                        leaders.pop()
                        leader_names.pop()
                        placed.pop()
                    backtracks += 1
            finally:
                staged.pop(first_index, None)
                leaders.pop()
                leader_names.pop()
                placed.pop()
            backtracks += 1
        return False
'''

if text.count(old_helper) != 1:
    raise SystemExit(f"expected one old final-body helper, found {text.count(old_helper)}")
text = text.replace(old_helper, new_helper, 1)

old_entry = '''        item = order[depth]
        original_index, (symbol, name, longitude) = item
        current_body = name
        generated_here = False

        for box, path in viable_candidates(item, depth):
'''
new_entry = '''        if depth == len(order) - 2:
            return solve_final_pair(depth)

        item = order[depth]
        original_index, (symbol, name, longitude) = item
        current_body = name
        generated_here = False

        for box, path in viable_candidates(item, depth):
'''
if text.count(old_entry) != 1:
    raise SystemExit(f"expected one search entry block, found {text.count(old_entry)}")
text = text.replace(old_entry, new_entry, 1)

old_recursion = '''                if depth == len(order) - 2:
                    if solve_final_body(depth + 1):
                        return True
                elif forward_check(depth + 1) and search(depth + 1):
                    return True
'''
new_recursion = '''                if forward_check(depth + 1) and search(depth + 1):
                    return True
'''
if text.count(old_recursion) != 1:
    raise SystemExit(f"expected one old endgame recursion block, found {text.count(old_recursion)}")
text = text.replace(old_recursion, new_recursion, 1)

PATH.write_text(text)
print("Applied Planet Finder true two-body endgame solver patch")
