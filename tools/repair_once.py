from pathlib import Path
import subprocess

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = """                f"{' > '.join(item[1] for item in group_items)} "
"""
new = """                f"{' > '.join(item[1][1] for item in group_items)} "
"""
if text.count(old) != 1:
    raise SystemExit(
        "Safety stop: expected exactly one malformed diagnostic line; "
        f"found {text.count(old)}"
    )
text = text.replace(old, new, 1)

old = """            diagnostic_print(
                f"Planet Finder {mode}: conjunction diagnostics group {group_index + 1} "
                f"{' > '.join(item[1][1] for item in group_items)} "
                f"rejections={diagnostic_rejections}",
                flush=True,
            )
"""
new = """            diagnostic_print(
                f"Planet Finder {mode}: conjunction diagnostics group {group_index + 1} "
                f"{' > '.join(item[1][1] for item in group_items)} "
                f"rejections={diagnostic_rejections}",
                level=1,
                flush=True,
            )
"""
if text.count(old) != 1:
    raise SystemExit(
        "Safety stop: expected exactly one corrected diagnostic block; "
        f"found {text.count(old)}"
    )
text = text.replace(old, new, 1)

path.write_text(text)

script = Path(__file__)
script_text = script.read_text()
script.write_text(script_text.replace("ENABLED = True", "ENABLED = False", 1))

subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", "tools/planet_finder_search_core.py", "tools/repair_once.py"], check=True)
subprocess.run(["git", "commit", "-m", "Fix conjunction diagnostic output"], check=True)
subprocess.run(["git", "push", "origin", "HEAD"], check=True)

print("Conjunction diagnostics fixed; 0.25 refinement unchanged.")
