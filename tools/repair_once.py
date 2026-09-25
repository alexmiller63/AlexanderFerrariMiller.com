from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

start_marker = '''        # Paired Child -> Grandchild look-ahead. An individually viable Child
'''
end_marker = '''        return True

    def search(depth):
'''

start = text.find(start_marker)
end = text.find(end_marker, start)

if start < 0 or end < 0:
    raise SystemExit("Safety stop: Child -> Grandchild forward-check block not found")

replacement = '''        # Child -> Grandchild look-ahead intentionally disabled.
        # Individual future-body witness checks remain active above.
        # Ordinary DFS now owns all multi-body compatibility decisions.

'''

text = text[:start] + replacement + text[end:]
path.write_text(text)
print("Disabled Child -> Grandchild forward look-ahead; individual forward checks remain.")
