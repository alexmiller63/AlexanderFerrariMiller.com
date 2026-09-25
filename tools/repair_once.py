from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

pair_start = text.find("    def solve_final_pair(first_depth):\n")
search_start = text.find("    def search(depth):\n", pair_start)
if pair_start < 0 or search_start < 0:
    raise SystemExit("Safety stop: special-endgame block boundary not found")

text = text[:pair_start] + text[search_start:]

special = '''        if depth == len(order) - 4:
            return solve_final_four(depth)

        if depth == len(order) - 2:
            return solve_final_pair(depth)

'''

if text.count(special) != 1:
    raise SystemExit(
        f"Safety stop: expected special-endgame dispatch exactly once; found {text.count(special)}"
    )

text = text.replace(special, "", 1)
path.write_text(text)
print("Removed two-body and four-body special endgames; ordinary recursive DFS restored.")
