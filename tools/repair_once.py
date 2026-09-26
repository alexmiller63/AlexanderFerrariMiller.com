from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_geometry.py")
text = path.read_text()

old = '''    def segment_clear(a, b, skip_start_escape=False) -> bool:
        for obstacle_index, box in enumerate(obstacles):
            if skip_start_escape and obstacle_index < allow_initial_escape_count and box.left <= a[0] <= box.right and box.top <= a[1] <= box.bottom:
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return False
        return True

    if segment_clear(anchor, center, skip_start_escape=True):
        return [anchor, center]
'''

new = '''    def segment_clear(a, b, skip_start_escape=False) -> bool:
        for obstacle_index, box in enumerate(obstacles):
            if skip_start_escape and obstacle_index < allow_initial_escape_count and box.left <= a[0] <= box.right and box.top <= a[1] <= box.bottom:
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return False
        return True

    def route_clear_of_target(path) -> bool:
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

    if segment_clear(anchor, center, skip_start_escape=True):
        candidate = [anchor, center]
        if route_clear_of_target(candidate):
            return candidate
'''

if text.count(old) != 1:
    raise SystemExit(f"Safety stop: expected route block once; found {text.count(old)}")
text = text.replace(old, new, 1)

old = '''        if segment_clear(elbow1, elbow2) and segment_clear(elbow2, center):
            return [anchor, elbow1, elbow2, center]
    return None
'''

new = '''        if segment_clear(elbow1, elbow2) and segment_clear(elbow2, center):
            candidate = [anchor, elbow1, elbow2, center]
            if route_clear_of_target(candidate):
                return candidate
    return None
'''

if text.count(old) != 1:
    raise SystemExit(f"Safety stop: expected elbow return block once; found {text.count(old)}")

path.write_text(text.replace(old, new, 1))
print("Target-label leader rejection installed.")
