from pathlib import Path
import subprocess

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''                rows.append((x, y, box))
                if len(rows) >= 80:
                    break
            rows.sort(key=lambda row: math.hypot(row[0] - natural[0], row[1] - natural[1]))
            if not rows:
                return None
            pools[name] = rows
'''
new = '''                rows.append((x, y, box))
            rows.sort(key=lambda row: math.hypot(row[0] - natural[0], row[1] - natural[1]))
            rows = rows[:80]
            if not rows:
                return None
            pools[name] = rows
'''

if text.count(old) != 1:
    raise SystemExit(
        "Safety stop: expected exactly one conjunction candidate-cap block; "
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
subprocess.run(["git", "commit", "-m", "Rank conjunction candidates before applying cap"], check=True)
subprocess.run(["git", "push", "origin", "HEAD"], check=True)

print("Conjunction candidates now all generate and sort before the best 80 are kept; 0.25 refinement unchanged; switch OFF.")
