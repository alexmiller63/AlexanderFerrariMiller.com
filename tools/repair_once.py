from pathlib import Path
import subprocess

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

changes = [
(
"""            for x, y, box in legal_candidate_positions(
                    longitude, w, h, reserved, displacement_scale):
""",
"""            # Tight conjunctions use the finest existing refinement.
            # Ordinary DFS remains on its caller-supplied scale.
            conjunction_displacement_scale = 0.25
            for x, y, box in legal_candidate_positions(
                    longitude, w, h, reserved, conjunction_displacement_scale):
"""
),
(
"""                if leader_hits_zodiac_rim(path_candidate) or leaders_too_close(
                        path_candidate, leaders + list(chosen_paths.values())):
                    chosen.pop(name, None)
                    continue
""",
"""                # Sibling leaders inside one atomic conjunction may begin close
                # because the anchors share nearly the same lambda.  External
                # leader clearance remains enforced.
                if leader_hits_zodiac_rim(path_candidate) or leaders_too_close(
                        path_candidate, leaders):
                    chosen.pop(name, None)
                    continue
"""
),
]

for old, new in changes:
    if text.count(old) != 1:
        raise SystemExit(
            "Safety stop: expected exactly one target occurrence; "
            f"found {text.count(old)}"
        )
    text = text.replace(old, new, 1)

path.write_text(text)

# Repair Once must CREATE the code change in the repository, not merely
# modify the ephemeral Actions workspace.
script = Path(__file__)
script_text = script.read_text()
if "ENABLED = True" not in script_text:
    raise SystemExit("Safety stop: could not locate Repair Once enable flag.")
script.write_text(script_text.replace("ENABLED = True", "ENABLED = False", 1))

subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", "tools/planet_finder_search_core.py", "tools/repair_once.py"], check=True)
subprocess.run(["git", "commit", "-m", "Fix atomic conjunction label refinement"], check=True)
subprocess.run(["git", "push", "origin", "HEAD"], check=True)

print("Repair Once created and pushed the conjunction fix; 0.25 refinement preserved and the switch is now OFF.")
