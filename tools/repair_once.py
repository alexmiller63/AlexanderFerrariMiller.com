from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''        longitude_by_name = {
            item[1][1]: item[1][2]
            for item in order
        }
'''
new = '''        # Diagnostics may contain conjunction/alignment bodies that were
        # solved and removed from the ordinary DFS order.  Longitudes therefore
        # come from the authoritative full input, not the reduced DFS order.
        longitude_by_name = {
            name: longitude
            for _, name, longitude in bodies
        }
'''

if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: expected diagnostic longitude map once; found {text.count(old)}"
    )

path.write_text(text.replace(old, new, 1))
print("Terminal diagnostics now resolve longitudes from all input bodies.")
