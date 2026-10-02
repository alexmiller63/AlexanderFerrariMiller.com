#!/usr/bin/env python3
"""One-shot: install blocker-directed recursive leader routing."""

from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_geometry.py")
text = P.read_text(encoding="utf-8")
start = text.find("\ndef route(")
if start < 0 or text.find("\ndef route(", start + 1) >= 0:
    raise SystemExit("Safety stop: route() missing or non-unique")

new_route = r'''
def route(anchor: tuple[float, float], center: tuple[float, float], obstacles: list[Box], diagnostic=None, allow_initial_escape_count: int = 0, prefix_cache: dict | None = None, allow_initial_escape_indices: set[int] | None = None, target_box: Box | None = None, allow_angular_escape: bool = False, existing_paths: list[list[tuple[float, float]]] | None = None) -> list[tuple[float, float]] | None:
    """Blocker-directed recursive leader routing for one fixed label position.

    Aim directly at the label.  When the desired segment is blocked, branch
    only around the blocking geometry (left/right), then recurse.  The outer
    Planet Finder DFS sees failure only after this small local search is
    exhausted.
    """
    existing_paths = existing_paths or []
    if allow_initial_escape_indices is None:
        initial_escape_indices = set(range(allow_initial_escape_count))
    else:
        initial_escape_indices = set(allow_initial_escape_indices)

    def inside_escape_zone(point, box):
        return (
            box.left - IMMUTABLE_LEADER_CLEARANCE <= point[0] <= box.right + IMMUTABLE_LEADER_CLEARANCE
            and box.top - IMMUTABLE_LEADER_CLEARANCE <= point[1] <= box.bottom + IMMUTABLE_LEADER_CLEARANCE
        )

    if any(
        i not in initial_escape_indices
        and b.left <= anchor[0] <= b.right
        and b.top <= anchor[1] <= b.bottom
        for i, b in enumerate(obstacles)
    ):
        if diagnostic is not None:
            diagnostic["anchor_blocked"] = diagnostic.get("anchor_blocked", 0) + 1
        return None

    def target_landing(source):
        if target_box is None:
            return center
        dx, dy = target_box.x - source[0], target_box.y - source[1]
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            return None
        t0, t1 = 0.0, 1.0
        for p, q in (
            (-dx, source[0] - target_box.left),
            ( dx, target_box.right - source[0]),
            (-dy, source[1] - target_box.top),
            ( dy, target_box.bottom - source[1]),
        ):
            if abs(p) < 1e-12:
                if q < 0:
                    return None
                continue
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
            if t0 > t1:
                return None
        hit = (source[0] + t0 * dx, source[1] + t0 * dy)
        vx, vy = hit[0] - source[0], hit[1] - source[1]
        d = math.hypot(vx, vy)
        if d <= 2.0:
            return source
        s = (d - 2.0) / d
        return source[0] + vx * s, source[1] + vy * s

    def obstacle_blocker(a, b, first):
        best = None
        seglen = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        for i, box in enumerate(obstacles):
            if first and i in initial_escape_indices and inside_escape_zone(a, box):
                continue
            if not segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                continue
            # Rank approximately by distance from source to box center.
            rank = math.hypot(box.x - a[0], box.y - a[1]) / seglen
            if best is None or rank < best[0]:
                best = (rank, "box", i, box)
        return best

    def leader_blocker(a, b):
        best = None
        for pi, other in enumerate(existing_paths):
            close_anchors = math.hypot(anchor[0] - other[0][0], anchor[1] - other[0][1]) < LEADER_TO_LEADER_CLEARANCE
            for si in range(len(other) - 1):
                if close_anchors and a == anchor and si == 0:
                    continue
                c, d = other[si], other[si + 1]
                dist = segment_distance(a, b, c, d)
                if dist >= LEADER_TO_LEADER_CLEARANCE:
                    continue
                # Rank by projection of blocker midpoint along desired segment.
                vx, vy = b[0] - a[0], b[1] - a[1]
                denom = vx * vx + vy * vy or 1.0
                mx, my = (c[0] + d[0]) / 2, (c[1] + d[1]) / 2
                t = ((mx - a[0]) * vx + (my - a[1]) * vy) / denom
                if best is None or t < best[0]:
                    best = (t, "leader", (pi, si), (c, d))
        return best

    def first_blocker(a, b, first):
        candidates = [x for x in (obstacle_blocker(a, b, first), leader_blocker(a, b)) if x is not None]
        return min(candidates, key=lambda x: x[0]) if candidates else None

    def bypass_points(a, b, blocker):
        kind = blocker[1]
        clearance = max(IMMUTABLE_LEADER_CLEARANCE, LEADER_TO_LEADER_CLEARANCE) + 6.0
        if kind == "box":
            box = blocker[3]
            corners = (
                (box.left - clearance, box.top - clearance),
                (box.right + clearance, box.top - clearance),
                (box.right + clearance, box.bottom + clearance),
                (box.left - clearance, box.bottom + clearance),
            )
            # Pick one corner on each side of the desired segment, nearest first.
            vx, vy = b[0] - a[0], b[1] - a[1]
            sides = {1: [], -1: []}
            for p in corners:
                cross = vx * (p[1] - a[1]) - vy * (p[0] - a[0])
                side = 1 if cross >= 0 else -1
                sides[side].append((math.hypot(p[0] - a[0], p[1] - a[1]), p))
            out = []
            for side in (1, -1):
                if sides[side]:
                    out.append(min(sides[side])[1])
            return out

        c, d = blocker[3]
        mx, my = (c[0] + d[0]) / 2, (c[1] + d[1]) / 2
        dx, dy = d[0] - c[0], d[1] - c[1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        # Bypass just beyond either side of the blocking leader segment.
        reach = clearance + 0.5 * length
        return [
            (mx + nx * reach, my + ny * reach),
            (mx - nx * reach, my - ny * reach),
        ]

    max_depth = 4
    node_cap = 128
    nodes = 0
    dead = set()

    def partial_legal(path):
        if leader_hits_zodiac_rim(path):
            return False
        if existing_paths and leaders_too_close(path, existing_paths):
            return False
        return True

    def solve(path, depth):
        nonlocal nodes
        nodes += 1
        if nodes > node_cap or depth > max_depth:
            return None
        source = path[-1]
        landing = target_landing(source)
        if landing is None:
            return None

        state = (round(source[0], 3), round(source[1], 3), depth)
        if state in dead:
            return None

        blocker = first_blocker(source, landing, len(path) == 1)
        if blocker is None:
            candidate = path + [landing]
            if partial_legal(candidate):
                return candidate
            dead.add(state)
            return None

        if diagnostic is not None:
            key = "directed_box_blocked" if blocker[1] == "box" else "directed_leader_blocked"
            diagnostic[key] = diagnostic.get(key, 0) + 1

        for waypoint in bypass_points(source, landing, blocker):
            # The segment to the bypass itself must be legal; if it has another
            # blocker, recurse toward the bypass by treating it as the next
            # local destination would recreate a general maze search. Instead
            # prune it and try the opposite side; subsequent recursion resumes
            # aiming at the real label.
            if first_blocker(source, waypoint, len(path) == 1) is not None:
                continue
            partial = path + [waypoint]
            if not partial_legal(partial):
                continue
            result = solve(partial, depth + 1)
            if result is not None:
                return result

        dead.add(state)
        return None

    result = solve([anchor], 0)
    if diagnostic is not None:
        diagnostic["recursive_nodes"] = diagnostic.get("recursive_nodes", 0) + nodes
        if result is None:
            diagnostic["route_failed"] = diagnostic.get("route_failed", 0) + 1
    return result
'''

P.write_text(text[:start] + "\n" + new_route.lstrip("\n"), encoding="utf-8")

me = Path(__file__)
source = me.read_text(encoding="utf-8")
needle = "\nENABLED = True\n"
if source.count(needle) != 1:
    raise SystemExit("Safety stop: ENABLED assignment not unique")
me.write_text(source.replace(needle, "\nENABLED = False\n", 1), encoding="utf-8")
print("Installed blocker-directed recursive leader solver (depth 4, 128-node cap); Repair Once is OFF.")
