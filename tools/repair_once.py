from pathlib import Path

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''            sun = next(item for item in sun_venus if item[1][1] == "Sun")
            venus = next(item for item in sun_venus if item[1][1] == "Venus")
            items = [sun, venus, others[0], others[1]]
'''

new = '''            sun = next(item for item in sun_venus if item[1][1] == "Sun")
            venus = next(item for item in sun_venus if item[1][1] == "Venus")
            items = [venus, sun, others[0], others[1]]
'''

count = text.count(old)
if count != 1:
    raise SystemExit(
        f"Safety stop: expected Sun+Venus ordering exactly once; found {count}"
    )

path.write_text(text.replace(old, new, 1))
print("Venus+Sun-first four-body endgame repair installed successfully.")
