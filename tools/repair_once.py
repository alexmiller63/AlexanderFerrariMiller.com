from pathlib import Path
import subprocess

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''            return all(a < b for a, b in zip(angles, angles[1:]))
'''
new = '''            # Preserve circular lambda order, but allow conjunction siblings
            # to share the same label-center angle at different radii.
            return all(a <= b for a, b in zip(angles, angles[1:]))
'''

if text.count(old) != 1:
    raise SystemExit(
        "Safety stop: expected exactly one strict conjunction lambda-order check; "
        f"found {text.count(old)}"
    )

text = text.replace(old, new, 1)
path.write_text(text)

script = Path(__file__)
script_text = script.read_text()
if "ENABLED = True" not in script_text:
    raise SystemExit("Safety stop: could not locate Repair Once enable flag.")
script.write_text(script_text.replace("ENABLED = True", "ENABLED = False", 1))

subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", "tools/planet_finder_search_core.py", "tools/repair_once.py"], check=True)
subprocess.run(["git", "commit", "-m", "Allow tied conjunction label angles"], check=True)
subprocess.run(["git", "push", "origin", "HEAD"], check=True)

print("Conjunction label centers may now tie in angle without reversing circular lambda order; 0.25 refinement unchanged; switch OFF.")
