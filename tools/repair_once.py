from pathlib import Path
import subprocess

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

geometry = Path("tools/planet_finder_geometry.py")
gtext = geometry.read_text()

old_anchor = '''    # A leader may not originate inside another placed label. Record this
    # explicit rejection for diagnostics before attempting any route.
    if any(box.left <= anchor[0] <= box.right and box.top <= anchor[1] <= box.bottom
           for box in obstacles[:allow_initial_escape_count + 1]):
        if diagnostic is not None:
            diagnostic["anchor_blocked"] = diagnostic.get("anchor_blocked", 0) + 1
        return None

    def segment_clear(a, b, skip_start_escape=False) -> bool:
        for obstacle_index, box in enumerate(obstacles):
            if skip_start_escape and obstacle_index < allow_initial_escape_count and box.left <= a[0] <= box.right and box.top <= a[1] <= box.bottom:
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return False
        return True
'''
new_anchor = '''    def inside_escape_zone(point, box) -> bool:
        # Initial escape is allowed only when the leader actually starts inside
        # the protected footprint of an explicitly escapable reserved label.
        # This exception applies to the first segment only; all later segments
        # still treat the label as a hard obstacle.
        return (
            box.left - IMMUTABLE_LEADER_CLEARANCE <= point[0] <= box.right + IMMUTABLE_LEADER_CLEARANCE
            and box.top - IMMUTABLE_LEADER_CLEARANCE <= point[1] <= box.bottom + IMMUTABLE_LEADER_CLEARANCE
        )

    # A leader may not originate inside a non-escapable obstacle such as an
    # already placed body label. The first allow_initial_escape_count obstacles
    # are explicitly reserved for first-segment escape handling below.
    if any(box.left <= anchor[0] <= box.right and box.top <= anchor[1] <= box.bottom
           for box in obstacles[allow_initial_escape_count:]):
        if diagnostic is not None:
            diagnostic["anchor_blocked"] = diagnostic.get("anchor_blocked", 0) + 1
        return None

    def segment_clear(a, b, skip_start_escape=False) -> bool:
        for obstacle_index, box in enumerate(obstacles):
            if (skip_start_escape
                    and obstacle_index < allow_initial_escape_count
                    and inside_escape_zone(a, box)):
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return False
        return True
'''

old_blocker = '''    def first_blocker(a, b, skip_start_escape=False):
        for obstacle_index, box in enumerate(obstacles):
            if skip_start_escape and obstacle_index < allow_initial_escape_count and box.left <= a[0] <= box.right and box.top <= a[1] <= box.bottom:
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return obstacle_index
        return None
'''
new_blocker = '''    def first_blocker(a, b, skip_start_escape=False):
        for obstacle_index, box in enumerate(obstacles):
            if (skip_start_escape
                    and obstacle_index < allow_initial_escape_count
                    and inside_escape_zone(a, box)):
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return obstacle_index
        return None
'''

for old, new, label in (
    (old_anchor, new_anchor, "route initial-escape block"),
    (old_blocker, new_blocker, "route blocker diagnostic"),
):
    if gtext.count(old) != 1:
        raise SystemExit(f"Safety stop: expected exactly one {label}; found {gtext.count(old)}")
    gtext = gtext.replace(old, new, 1)
geometry.write_text(gtext)

core = Path("tools/planet_finder_search_core.py")
ctext = core.read_text()
old_call = '''                path_candidate = route(
                    anchor, (x, y), reserved + placed + other_boxes,
                    diagnostic=conjunction_route_diagnostics,
                    allow_initial_escape_count=3,
                )
'''
new_call = '''                path_candidate = route(
                    anchor, (x, y), reserved + placed + other_boxes,
                    diagnostic=conjunction_route_diagnostics,
                    # Atomic conjunction glyphs can be radially staggered under
                    # a zodiac label. Permit first-segment escape from any
                    # reserved box only when the anchor starts inside that
                    # box's protected footprint. Placed/sibling labels remain
                    # hard obstacles, and later leader segments still cannot
                    # cross zodiac labels.
                    allow_initial_escape_count=len(reserved),
                )
'''
if ctext.count(old_call) != 1:
    raise SystemExit(
        "Safety stop: expected exactly one conjunction route call with 3 escape obstacles; "
        f"found {ctext.count(old_call)}"
    )
ctext = ctext.replace(old_call, new_call, 1)
core.write_text(ctext)

script = Path(__file__)
script_text = script.read_text()
if "ENABLED = True" not in script_text:
    raise SystemExit("Safety stop: could not locate Repair Once enable flag.")
script.write_text(script_text.replace("ENABLED = True", "ENABLED = False", 1))

subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", "tools/planet_finder_geometry.py", "tools/planet_finder_search_core.py", "tools/repair_once.py"], check=True)
subprocess.run(["git", "commit", "-m", "Allow narrow conjunction zodiac initial escape"], check=True)
subprocess.run(["git", "push", "origin", "HEAD"], check=True)

print("Conjunction anchors may escape a reserved zodiac box on the first segment only when starting inside its protected footprint; ordinary DFS and 0.25 refinement unchanged; switch OFF.")
