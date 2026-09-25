from pathlib import Path

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''        items = order[first_depth:first_depth + 4]
        names = [item[1][1] for item in items]
'''

new = '''        items = order[first_depth:first_depth + 4]

        # W2 shows that leaving Sun+Venus until after the other endgame pair
        # can consume all geometry in which Venus is viable.  When both are in
        # the final four, make Sun+Venus the first pair and leave the other two
        # bodies as the second pair.  This changes only endgame enumeration;
        # the squeaky-wheel ordering used above this boundary is untouched.
        sun_venus = [item for item in items if item[1][1] in ("Sun", "Venus")]
        others = [item for item in items if item[1][1] not in ("Sun", "Venus")]
        if len(sun_venus) == 2 and len(others) == 2:
            sun = next(item for item in sun_venus if item[1][1] == "Sun")
            venus = next(item for item in sun_venus if item[1][1] == "Venus")
            items = [sun, venus, others[0], others[1]]

        names = [item[1][1] for item in items]
'''

count = text.count(old)
if count != 1:
    raise SystemExit(
        f"Safety stop: expected final-four item setup exactly once; found {count}"
    )

path.write_text(text.replace(old, new, 1))
print("Sun+Venus-first four-body endgame repair installed successfully.")
