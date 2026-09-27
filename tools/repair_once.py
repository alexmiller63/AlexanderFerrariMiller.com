from pathlib import Path
import subprocess

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

geometry = Path("tools/planet_finder_geometry.py")
gtext = geometry.read_text()

old_direct = '''    if segment_clear(anchor, center, skip_start_escape=True):
        candidate = [anchor, center]
        if route_clear_of_target(candidate):
            return candidate
'''
new_direct = '''    if segment_clear(anchor, center, skip_start_escape=True):
        candidate = [anchor, center]
        if route_clear_of_target(candidate):
            return candidate
        if diagnostic is not None:
            diagnostic["target_approach"] = diagnostic.get("target_approach", 0) + 1
    elif diagnostic is not None:
        diagnostic["direct_blocked"] = diagnostic.get("direct_blocked", 0) + 1
'''

old_loop = '''        if not prefix_cache[key1]:
            continue
        if segment_clear(elbow1, elbow2) and segment_clear(elbow2, center):
            candidate = [anchor, elbow1, elbow2, center]
            if route_clear_of_target(candidate):
                return candidate
    return None
'''
new_loop = '''        if not prefix_cache[key1]:
            if diagnostic is not None:
                diagnostic["escape_blocked"] = diagnostic.get("escape_blocked", 0) + 1
            continue
        if not segment_clear(elbow1, elbow2):
            if diagnostic is not None:
                diagnostic["arc_blocked"] = diagnostic.get("arc_blocked", 0) + 1
            continue
        if not segment_clear(elbow2, center):
            if diagnostic is not None:
                diagnostic["final_blocked"] = diagnostic.get("final_blocked", 0) + 1
            continue
        candidate = [anchor, elbow1, elbow2, center]
        if route_clear_of_target(candidate):
            return candidate
        if diagnostic is not None:
            diagnostic["target_approach"] = diagnostic.get("target_approach", 0) + 1
    return None
'''

for old, new, label in (
    (old_direct, new_direct, "direct route block"),
    (old_loop, new_loop, "elbow route block"),
):
    if gtext.count(old) != 1:
        raise SystemExit(f"Safety stop: expected exactly one {label}; found {gtext.count(old)}")
    gtext = gtext.replace(old, new, 1)
geometry.write_text(gtext)

core = Path("tools/planet_finder_search_core.py")
ctext = core.read_text()

old_diag = '''        diagnostic_rejections = {
            "label_overlap": 0,
            "lambda_order": 0,
            "route": 0,
            "leader_label": 0,
            "leader_rim_or_external": 0,
            "sibling_leader_label": 0,
        }
'''
new_diag = old_diag + '''        conjunction_route_diagnostics = {}
'''

old_call = '''                path_candidate = route(
                    anchor, (x, y), reserved + placed + other_boxes,
                    allow_initial_escape_count=3,
                )
'''
new_call = '''                path_candidate = route(
                    anchor, (x, y), reserved + placed + other_boxes,
                    diagnostic=conjunction_route_diagnostics,
                    allow_initial_escape_count=3,
                )
'''

old_print = '''                f"pool_sizes={{{', '.join(f'{name!r}: {len(rows)}' for name, rows in pools.items())}}} "
                f"rejections={diagnostic_rejections}",
'''
new_print = '''                f"pool_sizes={{{', '.join(f'{name!r}: {len(rows)}' for name, rows in pools.items())}}} "
                f"rejections={diagnostic_rejections} "
                f"route_detail={conjunction_route_diagnostics}",
'''

for old, new, label in (
    (old_diag, new_diag, "conjunction diagnostic block"),
    (old_call, new_call, "conjunction route call"),
    (old_print, new_print, "conjunction failure print"),
):
    if ctext.count(old) != 1:
        raise SystemExit(f"Safety stop: expected exactly one {label}; found {ctext.count(old)}")
    ctext = ctext.replace(old, new, 1)
core.write_text(ctext)

script = Path(__file__)
script_text = script.read_text()
script.write_text(script_text.replace("ENABLED = True", "ENABLED = False", 1))

subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", "tools/planet_finder_geometry.py", "tools/planet_finder_search_core.py", "tools/repair_once.py"], check=True)
subprocess.run(["git", "commit", "-m", "Add compact conjunction route failure summary"], check=True)
subprocess.run(["git", "push", "origin", "HEAD"], check=True)

print("Compact conjunction route diagnostics installed; no solver geometry changed; switch OFF.")
