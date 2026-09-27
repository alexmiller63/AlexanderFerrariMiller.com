from pathlib import Path
import subprocess

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

geometry = Path("tools/planet_finder_geometry.py")
gtext = geometry.read_text()

old_signature = '''def route(anchor: tuple[float, float], center: tuple[float, float], obstacles: list[Box], diagnostic=None, allow_initial_escape_count: int = 0, prefix_cache: dict | None = None) -> list[tuple[float, float]] | None:
    if prefix_cache is None:
        prefix_cache = {}
'''
new_signature = '''def route(anchor: tuple[float, float], center: tuple[float, float], obstacles: list[Box], diagnostic=None, allow_initial_escape_count: int = 0, prefix_cache: dict | None = None, allow_initial_escape_indices: set[int] | None = None) -> list[tuple[float, float]] | None:
    if prefix_cache is None:
        prefix_cache = {}
    # Ordinary callers keep the historical contiguous prefix behavior. Atomic
    # conjunctions may instead name exactly which local obstacles are escapable
    # on the first segment, so placed labels never become escapable by accident.
    if allow_initial_escape_indices is None:
        initial_escape_indices = set(range(allow_initial_escape_count))
    else:
        initial_escape_indices = set(allow_initial_escape_indices)
'''

old_anchor = '''    # A leader may not originate inside a non-escapable obstacle such as an
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

    def first_blocker(a, b, skip_start_escape=False):
        for obstacle_index, box in enumerate(obstacles):
            if (skip_start_escape
                    and obstacle_index < allow_initial_escape_count
                    and inside_escape_zone(a, box)):
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return obstacle_index
        return None
'''
new_anchor = '''    # A leader may not originate inside a non-escapable obstacle. Explicitly
    # escapable obstacles are ignored only for the first segment and only when
    # the anchor really starts inside their protected footprint.
    if any(
        obstacle_index not in initial_escape_indices
        and box.left <= anchor[0] <= box.right
        and box.top <= anchor[1] <= box.bottom
        for obstacle_index, box in enumerate(obstacles)
    ):
        if diagnostic is not None:
            diagnostic["anchor_blocked"] = diagnostic.get("anchor_blocked", 0) + 1
        return None

    def segment_clear(a, b, skip_start_escape=False) -> bool:
        for obstacle_index, box in enumerate(obstacles):
            if (skip_start_escape
                    and obstacle_index in initial_escape_indices
                    and inside_escape_zone(a, box)):
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return False
        return True

    def first_blocker(a, b, skip_start_escape=False):
        for obstacle_index, box in enumerate(obstacles):
            if (skip_start_escape
                    and obstacle_index in initial_escape_indices
                    and inside_escape_zone(a, box)):
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return obstacle_index
        return None
'''

for old, new, label in (
    (old_signature, new_signature, "route signature"),
    (old_anchor, new_anchor, "route initial-escape logic"),
):
    if gtext.count(old) != 1:
        raise SystemExit(f"Safety stop: expected exactly one {label}; found {gtext.count(old)}")
    gtext = gtext.replace(old, new, 1)
geometry.write_text(gtext)

core = Path("tools/planet_finder_search_core.py")
ctext = core.read_text()
old_call = '''                other_boxes = [other[2] for other_name, other in chosen.items() if other_name != name]
                path_candidate = route(
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
new_call = '''                other_boxes = [other[2] for other_name, other in chosen.items() if other_name != name]
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
if ctext.count(old_call) != 1:
    raise SystemExit(
        "Safety stop: expected exactly one current conjunction route call; "
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
subprocess.run(["git", "commit", "-m", "Treat conjunction-local labels as first-segment escape obstacles"], check=True)
subprocess.run(["git", "push", "origin", "HEAD"], check=True)

print("Conjunction-local first-segment escape installed: reserved and sibling labels are escapable only when the anchor starts inside them; placed labels remain hard; ordinary DFS and 0.25 refinement unchanged; switch OFF.")
