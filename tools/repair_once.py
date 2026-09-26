from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search.py")
text = path.read_text()
old = '''        if sticky_promote_body is None:
            sticky_promote_body = outcome.blocker
        promote_body = sticky_promote_body
'''
new = '''        sticky_promote_body = outcome.blocker
        promote_body = outcome.blocker
'''

if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: expected blocker-selection block exactly once; found {text.count(old)}"
    )

path.write_text(text.replace(old, new, 1))
print("Changed squeaky-wheel promotion to follow the current blocker.")
