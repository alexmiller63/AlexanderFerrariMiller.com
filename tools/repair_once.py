from pathlib import Path

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''        if depth == len(order) - 2:
            return solve_final_pair(depth)
'''

new = '''        # Start the coupled endgame with four bodies remaining.
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

count = text.count(old)

if count != 1:
    raise SystemExit(
        f"Safety stop: expected endgame trigger exactly once; found {count}"
    )

path.write_text(text.replace(old, new, 1))

print("Four-body endgame instrumentation installed successfully.")
