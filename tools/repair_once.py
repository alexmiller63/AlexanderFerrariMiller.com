from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''                if forward_check(depth + 1) and search(depth + 1):
                    return True
'''
new = '''                if search(depth + 1):
                    return True
'''

count = text.count(old)
if count != 1:
    raise SystemExit(
        f"Safety stop: expected forward-check DFS call exactly once; found {count}"
    )

text = text.replace(old, new, 1)
path.write_text(text)
print("Disabled forward checking; ordinary recursive DFS now owns future-body compatibility.")
