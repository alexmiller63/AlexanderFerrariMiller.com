from pathlib import Path
import subprocess

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''        if not assign(0):
            diagnostic_print(
                f"Planet Finder {mode}: conjunction diagnostics group {group_index + 1} "
                f"{' > '.join(item[1][1] for item in group_items)} "
                f"rejections={diagnostic_rejections}",
                level=1,
                flush=True,
            )
            return None
'''
new = '''        if not assign(0):
            print(
                f"CONJUNCTION FAILURE mode={mode} group={group_index + 1} "
                f"bodies={' > '.join(item[1][1] for item in group_items)} "
                f"pool_sizes={{{', '.join(f'{name!r}: {len(rows)}' for name, rows in pools.items())}}} "
                f"rejections={diagnostic_rejections}",
                flush=True,
            )
            return None
'''

if text.count(old) != 1:
    raise SystemExit(
        "Safety stop: expected exactly one conjunction failure diagnostic block; "
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
subprocess.run(["git", "commit", "-m", "Use unconditional conjunction failure diagnostic"], check=True)
subprocess.run(["git", "push", "origin", "HEAD"], check=True)

print("Installed unconditional conjunction failure diagnostic; 0.25 conjunction refinement scale unchanged; switch OFF.")
