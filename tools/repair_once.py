from pathlib import Path

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

start = text.find("    def solve_final_four(first_depth):\n")
end = text.find("    def search(depth):\n", start)
if start < 0 or end < 0:
    raise SystemExit("Safety stop: solve_final_four/search boundary not found")

old = text[start:end]
new = '''    def solve_final_four(first_depth):
        """Solve the final four bodies as two pair units, then pair x pair."""
        nonlocal candidates, backtracks, current_body
        items = order[first_depth:first_depth + 4]
        names = [item[1][1] for item in items]
        diagnostic_print(
            f"Planet Finder {mode}: FOUR-BODY ENDGAME "
            f"pairs={names[0]}+{names[1]} / {names[2]}+{names[3]} "
            f"depth={first_depth}/{len(order)} pair-x-pair",
            level=1,
            flush=True,
        )

        def push(item, depth):
            nonlocal candidates, current_body
            original_index, (symbol, name, longitude) = item
            current_body = name
            for box, leader_path in viable_candidates(
                item,
                depth,
                consume_body_budget=False,
            ):
                candidates += 1
                placed.append(box)
                leaders.append(leader_path)
                leader_names.append(name)
                staged[original_index] = (symbol, name, longitude, box, leader_path)
                yield original_index
                staged.pop(original_index, None)
                leader_names.pop()
                leaders.pop()
                placed.pop()

        pair1_attempts = 0
        pair2_attempts = 0

        # Pair 1 is a unit: enumerate only complete A+B configurations.
        for first_index in push(items[0], first_depth):
            for second_index in push(items[1], first_depth + 1):
                pair1_attempts += 1

                # Pair 2 is independently completed against the same pre-endgame
                # geometry plus this complete Pair 1 configuration.  We do not
                # recurse into ordinary DFS between members of either pair.
                for third_index in push(items[2], first_depth + 2):
                    for fourth_index in push(items[3], first_depth + 3):
                        pair2_attempts += 1
                        if search(first_depth + 4):
                            diagnostic_print(
                                f"Planet Finder {mode}: FOUR-BODY SUCCESS "
                                f"pair1-tested={pair1_attempts} "
                                f"pair2-tested={pair2_attempts}",
                                level=1,
                                flush=True,
                            )
                            return True
                        backtracks += 1
                    backtracks += 1
                backtracks += 1
            backtracks += 1

        diagnostic_print(
            f"Planet Finder {mode}: FOUR-BODY EXHAUSTED "
            f"pair1-tested={pair1_attempts} pair2-tested={pair2_attempts}",
            level=1,
            flush=True,
        )
        return False

'''

text = text[:start] + new + text[end:]
path.write_text(text)
print("Four-body pair-x-pair endgame installed successfully.")
