from pathlib import Path
import subprocess

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

geometry = Path("tools/planet_finder_geometry.py")
gtext = geometry.read_text()

old_signature = '''def route(anchor: tuple[float, float], center: tuple[float, float], obstacles: list[Box], diagnostic=None, allow_initial_escape_count: int = 0, prefix_cache: dict | None = None, allow_initial_escape_indices: set[int] | None = None) -> list[tuple[float, float]] | None:
'''
new_signature = '''def route(anchor: tuple[float, float], center: tuple[float, float], obstacles: list[Box], diagnostic=None, allow_initial_escape_count: int = 0, prefix_cache: dict | None = None, allow_initial_escape_indices: set[int] | None = None, target_box: Box | None = None, allow_angular_escape: bool = False) -> list[tuple[float, float]] | None:
'''
if gtext.count(old_signature) != 1:
    raise SystemExit(f"Safety stop: expected exactly one route signature; found {gtext.count(old_signature)}")
gtext = gtext.replace(old_signature, new_signature, 1)

old_target = '''    def route_clear_of_target(path) -> bool:
        # The target label is the final obstacle. Earlier leader segments may
        # neither enter nor graze its protected rectangle. The final segment
        # is allowed to terminate at the label center, but must approach it
        # from outside rather than travel through the label first.
        if not obstacles or len(path) < 2:
            return True
        target = obstacles[-1]
        for i in range(len(path) - 2):
            if segment_hits_box(path[i], path[i + 1], target, IMMUTABLE_LEADER_CLEARANCE):
                return False
        a, b = path[-2], path[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 1e-12:
            return False
        epsilon = min(1.0, length / 2.0)
        before = (b[0] - dx / length * epsilon, b[1] - dy / length * epsilon)
        return not (
            target.left - IMMUTABLE_LEADER_CLEARANCE <= before[0] <= target.right + IMMUTABLE_LEADER_CLEARANCE
            and target.top - IMMUTABLE_LEADER_CLEARANCE <= before[1] <= target.bottom + IMMUTABLE_LEADER_CLEARANCE
        )
'''
new_target = '''    def route_clear_of_target(path) -> bool:
        # The caller may provide the actual label being routed to. Older
        # callers keep the historical fallback until they are migrated, but
        # conjunction routing never infers its target from obstacle ordering.
        target = target_box
        if target is None:
            target = obstacles[-1] if obstacles else None
        if target is None or len(path) < 2:
            return True
        for i in range(len(path) - 2):
            if segment_hits_box(path[i], path[i + 1], target, IMMUTABLE_LEADER_CLEARANCE):
                return False
        a, b = path[-2], path[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 1e-12:
            return False
        epsilon = min(1.0, length / 2.0)
        before = (b[0] - dx / length * epsilon, b[1] - dy / length * epsilon)
        return not (
            target.left - IMMUTABLE_LEADER_CLEARANCE <= before[0] <= target.right + IMMUTABLE_LEADER_CLEARANCE
            and target.top - IMMUTABLE_LEADER_CLEARANCE <= before[1] <= target.bottom + IMMUTABLE_LEADER_CLEARANCE
        )
'''
if gtext.count(old_target) != 1:
    raise SystemExit(f"Safety stop: expected exactly one route target block; found {gtext.count(old_target)}")
gtext = gtext.replace(old_target, new_target, 1)

old_loop = '''    anchor_theta = math.atan2(anchor[1] - CY, anchor[0] - CX)
    center_theta = math.atan2(center[1] - CY, center[0] - CX)
    for radius in ROUTE_RADII:
        elbow1 = (CX + radius * math.cos(anchor_theta), CY + radius * math.sin(anchor_theta))
        elbow2 = (CX + radius * math.cos(center_theta), CY + radius * math.sin(center_theta))
        key1 = (round(elbow1[0], 6), round(elbow1[1], 6))
        if key1 not in prefix_cache:
            prefix_cache[key1] = segment_clear(anchor, elbow1, skip_start_escape=True)
        if not prefix_cache[key1]:
            if diagnostic is not None:
                diagnostic["escape_blocked"] = diagnostic.get("escape_blocked", 0) + 1
                blocker = first_blocker(anchor, elbow1, skip_start_escape=True)
                if blocker is not None:
                    by_obstacle = diagnostic.setdefault("escape_blocked_by", {})
                    by_obstacle[blocker] = by_obstacle.get(blocker, 0) + 1
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
new_loop = '''    anchor_theta = math.atan2(anchor[1] - CY, anchor[0] - CX)
    center_theta = math.atan2(center[1] - CY, center[0] - CX)
    for radius in ROUTE_RADII:
        # Preserve the historical radial route first. For conjunctions only,
        # add bounded left/right first elbows using the existing quarter-label
        # refinement distance as the angular step. Every segment is still
        # collision checked; this routes around a sibling label rather than
        # declaring that label escapable.
        angular_step = (LABEL_LENGTH * 0.25) / max(radius, 1.0)
        offsets = (0.0,)
        if allow_angular_escape:
            offsets = (0.0, -angular_step, angular_step, -2.0 * angular_step, 2.0 * angular_step)
        for offset in offsets:
            elbow1_theta = anchor_theta + offset
            elbow1 = (CX + radius * math.cos(elbow1_theta), CY + radius * math.sin(elbow1_theta))
            elbow2 = (CX + radius * math.cos(center_theta), CY + radius * math.sin(center_theta))
            key1 = (round(elbow1[0], 6), round(elbow1[1], 6))
            if key1 not in prefix_cache:
                prefix_cache[key1] = segment_clear(anchor, elbow1, skip_start_escape=True)
            if not prefix_cache[key1]:
                if diagnostic is not None:
                    diagnostic["escape_blocked"] = diagnostic.get("escape_blocked", 0) + 1
                    blocker = first_blocker(anchor, elbow1, skip_start_escape=True)
                    if blocker is not None:
                        by_obstacle = diagnostic.setdefault("escape_blocked_by", {})
                        by_obstacle[blocker] = by_obstacle.get(blocker, 0) + 1
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
if gtext.count(old_loop) != 1:
    raise SystemExit(f"Safety stop: expected exactly one route elbow loop; found {gtext.count(old_loop)}")
gtext = gtext.replace(old_loop, new_loop, 1)
geometry.write_text(gtext)

core = Path("tools/planet_finder_search_core.py")
ctext = core.read_text()
old_call = '''                other_boxes = [other[2] for other_name, other in chosen.items() if other_name != name]
                conjunction_obstacles = reserved + placed + other_boxes
                sibling_start = len(reserved) + len(placed)
                conjunction_escape_indices = (
                    set(range(len(reserved)))
                    | set(range(sibling_start, sibling_start + len(other_boxes)))
                )
                path_candidate = route(
                    anchor, (x, y), conjunction_obstacles,
                    diagnostic=conjunction_route_diagnostics,
                    # Conjunction-local escape rule: reserved labels and sibling
                    # conjunction labels may be escaped on the first segment
                    # only when the anchor starts inside their protected box.
                    # Previously placed non-conjunction labels remain hard.
                    allow_initial_escape_indices=conjunction_escape_indices,
                )
'''
new_call = '''                other_boxes = [other[2] for other_name, other in chosen.items() if other_name != name]
                conjunction_obstacles = reserved + placed + other_boxes
                path_candidate = route(
                    anchor, (x, y), conjunction_obstacles,
                    diagnostic=conjunction_route_diagnostics,
                    # Reserved chart annotations may still be escaped only when
                    # the anchor begins inside their protected footprint.
                    # Sibling labels are hard obstacles; angular first elbows
                    # route around them instead of exempting collisions.
                    allow_initial_escape_indices=set(range(len(reserved))),
                    target_box=box,
                    allow_angular_escape=True,
                )
'''
if ctext.count(old_call) != 1:
    raise SystemExit(
        "Safety stop: expected exactly one conjunction-local route call; "
        f"found {ctext.count(old_call)}"
    )
ctext = ctext.replace(old_call, new_call, 1)
core.write_text(ctext)

script = Path(__file__)
script_text = script.read_text()
script.write_text(script_text.replace("ENABLED = True", "ENABLED = False", 1))

subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", "tools/planet_finder_geometry.py", "tools/planet_finder_search_core.py", "tools/repair_once.py"], check=True)
subprocess.run(["git", "commit", "-m", "Route conjunction leaders around sibling labels"], check=True)
subprocess.run(["git", "push", "origin", "HEAD"], check=True)

print("Architectural conjunction routing repair installed: explicit target label, sibling labels hard, bounded angular first elbows enabled for conjunctions, ordinary DFS and 0.25 refinement unchanged; switch OFF.")
