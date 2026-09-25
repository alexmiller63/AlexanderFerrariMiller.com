from pathlib import Path

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

start = text.find("    def search(depth):\n")
if start < 0:
    raise SystemExit("Safety stop: search() not found")

needle = '''        # Start the coupled endgame with four bodies remaining.
        # Solve them as two consecutive pairs instead of allowing ordinary DFS
        # to commit the first two bodies and leave only the final pair to fight
        # over the remaining geometry.
        if depth == len(order) - 4:
            diagnostic_print(
                f"Planet Finder {mode}: FOUR-BODY ENDGAME "
                f"pairs={order[depth][1][1]}+{order[depth + 1][1][1]} / "
                f"{order[depth + 2][1][1]}+{order[depth + 3][1][1]} "
                f"depth={depth}/{len(order)}",
                level=1,
                flush=True,
            )

        if depth == len(order) - 2:
            return solve_final_pair(depth)
'''

replacement = '''        if depth == len(order) - 4:
            return solve_final_four(depth)

        if depth == len(order) - 2:
            return solve_final_pair(depth)
'''

if text.count(needle) != 1:
    raise SystemExit(
        f"Safety stop: expected four-body instrumentation exactly once; found {text.count(needle)}"
    )

helper = '''    def solve_final_four(first_depth):
        """Couple the final four bodies so neither pair is committed in isolation."""
        nonlocal candidates, backtracks, current_body
        items = order[first_depth:first_depth + 4]
        names = [item[1][1] for item in items]
        diagnostic_print(
            f"Planet Finder {mode}: FOUR-BODY ENDGAME "
            f"pairs={names[0]}+{names[1]} / {names[2]}+{names[3]} "
            f"depth={first_depth}/{len(order)} coupled-search",
            level=1,
            flush=True,
        )

        def place_item(slot, continuation):
            nonlocal candidates, backtracks, current_body
            item = items[slot]
            original_index, (symbol, name, longitude) = item
            current_body = name
            for box, leader_path in viable_candidates(
                item,
                first_depth + slot,
                consume_body_budget=False,
            ):
                candidates += 1
                placed.append(box)
                leaders.append(leader_path)
                leader_names.append(name)
                staged[original_index] = (symbol, name, longitude, box, leader_path)
                try:
                    if continuation():
                        return True
                finally:
                    staged.pop(original_index, None)
                    leader_names.pop()
                    leaders.pop()
                    placed.pop()
                backtracks += 1
            return False

        # Enumerate the first pair, but for every complete first-pair geometry
        # immediately enumerate the second pair before abandoning that geometry.
        # This gives Ceres+Uranus and Sun+Venus one coupled four-body search tree.
        def fourth():
            return place_item(3, lambda: search(first_depth + 4))

        def third():
            return place_item(2, fourth)

        def second():
            return place_item(1, third)

        return place_item(0, second)

'''

text = text[:start] + helper + text[start:]
text = text.replace(needle, replacement, 1)
path.write_text(text)
print("Coupled four-body endgame installed successfully.")
