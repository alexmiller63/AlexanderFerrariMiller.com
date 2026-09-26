from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_geometry.py")
text = path.read_text()
old = '''    if len(current) > 1:
        groups.append(current)
    return groups
'''
new = '''    if len(current) > 1:
        groups.append(current)

    # Keep members of each conjunction in circular lambda order, but make the
    # list of independent conjunctions deterministic by the first member's
    # normalized longitude.  This prevents the arbitrary circular scan break
    # from rotating otherwise independent groups.
    groups.sort(key=lambda group: group[0][2] % 360.0)
    return groups
'''

if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: expected conjunction_groups return block exactly once; found {text.count(old)}"
    )

path.write_text(text.replace(old, new, 1))
print("Fixed deterministic ordering of independent conjunction groups.")
