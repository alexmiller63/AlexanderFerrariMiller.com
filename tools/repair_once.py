from pathlib import Path
import subprocess

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

geometry = Path("tools/planet_finder_geometry.py")
gtext = geometry.read_text()

old_helper = '''    def segment_clear(a, b, skip_start_escape=False) -> bool:
        for obstacle_index, box in enumerate(obstacles):
            if skip_start_escape and obstacle_index < allow_initial_escape_count and box.left <= a[0] <= box.right and box.top <= a[1] <= box.bottom:
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return False
        return True
'''
new_helper = '''    def segment_clear(a, b, skip_start_escape=False) -> bool:
        for obstacle_index, box in enumerate(obstacles):
            if skip_start_escape and obstacle_index < allow_initial_escape_count and box.left <= a[0] <= box.right and box.top <= a[1] <= box.bottom:
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return False
        return True

    def first_blocker(a, b, skip_start_escape=False):
        for obstacle_index, box in enumerate(obstacles):
            if skip_start_escape and obstacle_index < allow_initial_escape_count and box.left <= a[0] <= box.right and box.top <= a[1] <= box.bottom:
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return obstacle_index
        return None
'''

old_escape = '''        if not prefix_cache[key1]:
            if diagnostic is not None:
                diagnostic["escape_blocked"] = diagnostic.get("escape_blocked", 0) + 1
            continue
'''
new_escape = '''        if not prefix_cache[key1]:
            if diagnostic is not None:
                diagnostic["escape_blocked"] = diagnostic.get("escape_blocked", 0) + 1
                blocker = first_blocker(anchor, elbow1, skip_start_escape=True)
                if blocker is not None:
                    by_obstacle = diagnostic.setdefault("escape_blocked_by", {})
                    by_obstacle[blocker] = by_obstacle.get(blocker, 0) + 1
            continue
'''

for old, new, label in (
    (old_helper, new_helper, "segment-clear helper"),
    (old_escape, new_escape, "escape-block diagnostic"),
):
    if gtext.count(old) != 1:
        raise SystemExit(f"Safety stop: expected exactly one {label}; found {gtext.count(old)}")
    gtext = gtext.replace(old, new, 1)
geometry.write_text(gtext)

core = Path("tools/planet_finder_search_core.py")
ctext = core.read_text()

old_failure = '''        if not assign(0):
            print(
                f"CONJUNCTION FAILURE mode={mode} group={group_index + 1} "
                f"bodies={' > '.join(item[1][1] for item in group_items)} "
                f"pool_sizes={{{', '.join(f'{name!r}: {len(rows)}' for name, rows in pools.items())}}} "
                f"rejections={diagnostic_rejections} "
                f"route_detail={conjunction_route_diagnostics}",
                flush=True,
            )
            return None
'''
new_failure = '''        if not assign(0):
            raw_escape_blockers = conjunction_route_diagnostics.get("escape_blocked_by", {})
            blocker_counts = {}
            for obstacle_index, count in raw_escape_blockers.items():
                if obstacle_index < len(reserved_names):
                    label = reserved_names[obstacle_index]
                elif obstacle_index < len(reserved) + len(placed):
                    label = f"placed_{obstacle_index - len(reserved)}"
                else:
                    label = "conjunction_sibling_label"
                blocker_counts[label] = blocker_counts.get(label, 0) + count
            top_escape_blockers = dict(sorted(
                blocker_counts.items(), key=lambda item: (-item[1], item[0])
            )[:4])
            route_summary = {
                key: value for key, value in conjunction_route_diagnostics.items()
                if key != "escape_blocked_by"
            }
            print(
                f"CONJUNCTION FAILURE mode={mode} group={group_index + 1} "
                f"bodies={' > '.join(item[1][1] for item in group_items)} "
                f"pool_sizes={{{', '.join(f'{name!r}: {len(rows)}' for name, rows in pools.items())}}} "
                f"rejections={diagnostic_rejections} "
                f"route_detail={route_summary} "
                f"escape_blockers={top_escape_blockers}",
                flush=True,
            )
            return None
'''

if ctext.count(old_failure) != 1:
    raise SystemExit(
        "Safety stop: expected exactly one compact conjunction failure block; "
        f"found {ctext.count(old_failure)}"
    )
ctext = ctext.replace(old_failure, new_failure, 1)
core.write_text(ctext)

script = Path(__file__)
script_text = script.read_text()
script.write_text(script_text.replace("ENABLED = True", "ENABLED = False", 1))

subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", "tools/planet_finder_geometry.py", "tools/planet_finder_search_core.py", "tools/repair_once.py"], check=True)
subprocess.run(["git", "commit", "-m", "Identify conjunction escape blockers"], check=True)
subprocess.run(["git", "push", "origin", "HEAD"], check=True)

print("Compact conjunction escape-blocker names installed; solver geometry unchanged; switch OFF.")
