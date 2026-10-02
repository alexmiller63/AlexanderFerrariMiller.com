#!/usr/bin/env python3
"""One-shot: replace fixed leader enumeration with bounded recursive routing."""

from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_geometry.py")
text = P.read_text(encoding="utf-8")
start = text.find("\ndef route(")
if start < 0:
    raise SystemExit("Safety stop: route() not found")
if text.find("\ndef route(", start + 1) >= 0:
    raise SystemExit("Safety stop: route() is not unique")

new_route = r'''
def route(anchor: tuple[float, float], center: tuple[float, float], obstacles: list[Box], diagnostic=None, allow_initial_escape_count: int = 0, prefix_cache: dict | None = None, allow_initial_escape_indices: set[int] | None = None, target_box: Box | None = None, allow_angular_escape: bool = False, existing_paths: list[list[tuple[float, float]]] | None = None) -> list[tuple[float, float]] | None:
    """Find the simplest legal leader with a bounded recursive local search.

    Planet Finder chooses the label position.  This routine owns leader
    geometry for that fixed position.  A failed segment therefore backtracks
    inside the leader router before the outer layout DFS is allowed to reject
    the label candidate.

    Search order is deterministic and visually conservative:
      1. direct leader;
      2. one-elbow routes;
      3. two-elbow routes.

    Waypoints live on the existing canonical route radii and quarter-label
    angular lattice.  The recursion is deliberately shallow and memoized:
    this is constrained geometric routing, not an unrestricted maze search.
    """
    if prefix_cache is None:
        prefix_cache = {}
    existing_paths = existing_paths or []

    if allow_initial_escape_indices is None:
        initial_escape_indices = set(range(allow_initial_escape_count))
    else:
        initial_escape_indices = set(allow_initial_escape_indices)

    def inside_escape_zone(point, box) -> bool:
        return (
            box.left - IMMUTABLE_LEADER_CLEARANCE <= point[0] <= box.right + IMMUTABLE_LEADER_CLEARANCE
            and box.top - IMMUTABLE_LEADER_CLEARANCE <= point[1] <= box.bottom + IMMUTABLE_LEADER_CLEARANCE
        )

    if any(
        obstacle_index not in initial_escape_indices
        and box.left <= anchor[0] <= box.right
        and box.top <= anchor[1] <= box.bottom
        for obstacle_index, box in enumerate(obstacles)
    ):
        if diagnostic is not None:
            diagnostic["anchor_blocked"] = diagnostic.get("anchor_blocked", 0) + 1
        return None

    def segment_clear(a, b, *, first_segment=False) -> bool:
        for obstacle_index, box in enumerate(obstacles):
            if (
                first_segment
                and obstacle_index in initial_escape_indices
                and inside_escape_zone(a, box)
            ):
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return False
        return True

    def first_blocker(a, b, *, first_segment=False):
        for obstacle_index, box in enumerate(obstacles):
            if (
                first_segment
                and obstacle_index in initial_escape_indices
                and inside_escape_zone(a, box)
            ):
                continue
            if segment_hits_box(a, b, box, IMMUTABLE_LEADER_CLEARANCE):
                return obstacle_index
        return None

    def target_landing(source, target):
        if target is None:
            return center
        dx = target.x - source[0]
        dy = target.y - source[1]
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            return None
        t_enter, t_exit = 0.0, 1.0
        for p0, q0 in (
            (-dx, source[0] - target.left),
            ( dx, target.right - source[0]),
            (-dy, source[1] - target.top),
            ( dy, target.bottom - source[1]),
        ):
            if abs(p0) < 1e-12:
                if q0 < 0:
                    return None
                continue
            r = q0 / p0
            if p0 < 0:
                t_enter = max(t_enter, r)
            else:
                t_exit = min(t_exit, r)
            if t_enter > t_exit:
                return None
        if t_exit < 0.0 or t_enter > 1.0:
            return None
        hit = (source[0] + t_enter * dx, source[1] + t_enter * dy)
        hx, hy = hit[0] - source[0], hit[1] - source[1]
        distance = math.hypot(hx, hy)
        if distance <= 2.0 or distance < 1e-12:
            return source
        scale = (distance - 2.0) / distance
        return source[0] + hx * scale, source[1] + hy * scale

    def target_clear(path) -> bool:
        if target_box is None:
            return True
        if len(path) < 2:
            return False
        for i in range(len(path) - 2):
            if segment_hits_box(
                path[i], path[i + 1], target_box, IMMUTABLE_LEADER_CLEARANCE
            ):
                return False
        return not segment_hits_box(path[-2], path[-1], target_box, -0.5)

    def path_legal(path) -> bool:
        if not target_clear(path):
            return False
        if leader_hits_zodiac_rim(path):
            return False
        if existing_paths and leaders_too_close(path, existing_paths):
            if diagnostic is not None:
                diagnostic["existing_leader_blocked"] = diagnostic.get(
                    "existing_leader_blocked", 0
                ) + 1
            return False
        # A leader may not cross itself.  With at most two elbows this is cheap,
        # but keeping the invariant here makes future extension safe.
        if len(path) >= 4:
            for i in range(len(path) - 1):
                for j in range(i + 2, len(path) - 1):
                    if i == 0 and j == len(path) - 2:
                        continue
                    if segments_too_close(
                        path[i], path[i + 1], path[j], path[j + 1], 0.5
                    ):
                        return False
        return True

    def angular_offsets(radius):
        step = (LABEL_LENGTH * 0.25) / max(radius, 1.0)
        # Zero first, then symmetric quarter-label shells.
        yield 0.0
        for shell in range(1, 9):
            yield -shell * step
            yield shell * step

    anchor_theta = math.atan2(anchor[1] - CY, anchor[0] - CX)
    target_theta = math.atan2(center[1] - CY, center[0] - CX)

    def waypoint_family(theta):
        # Prefer smaller angular deflection before changing radius.  This keeps
        # leaders visually simple while still exposing the complete canonical
        # bounded lattice.
        for shell in range(0, 9):
            signs = (0.0,) if shell == 0 else (-1.0, 1.0)
            for sign in signs:
                for radius in ROUTE_RADII:
                    step = (LABEL_LENGTH * 0.25) / max(radius, 1.0)
                    angle = theta + sign * shell * step
                    yield (
                        CX + radius * math.cos(angle),
                        CY + radius * math.sin(angle),
                    )

    escape_waypoints = tuple(waypoint_family(anchor_theta))
    approach_waypoints = tuple(waypoint_family(target_theta))

    # Bound the recursive search independently of the outer Planet Finder
    # budget.  Memoization normally keeps this far below the cap; the cap is a
    # hard guard against accidental combinatorial growth.
    node_cap = 2048
    nodes = 0
    dead_states = set()

    def record_block(kind, a=None, b=None, *, first_segment=False):
        if diagnostic is None:
            return
        diagnostic[kind] = diagnostic.get(kind, 0) + 1
        if a is not None and b is not None:
            blocker = first_blocker(a, b, first_segment=first_segment)
            if blocker is not None:
                bucket = diagnostic.setdefault(kind + "_by", {})
                bucket[blocker] = bucket.get(blocker, 0) + 1

    def try_finish(path):
        source = path[-1]
        landing = target_landing(source, target_box)
        if landing is None:
            return None
        first = len(path) == 1
        if not segment_clear(source, landing, first_segment=first):
            record_block("final_blocked", source, landing, first_segment=first)
            return None
        candidate = path + [landing]
        if path_legal(candidate):
            return candidate
        if diagnostic is not None:
            diagnostic["target_approach"] = diagnostic.get("target_approach", 0) + 1
        return None

    def search(path, stage):
        nonlocal nodes
        nodes += 1
        if nodes > node_cap:
            if diagnostic is not None:
                diagnostic["recursive_node_cap"] = diagnostic.get(
                    "recursive_node_cap", 0
                ) + 1
            return None

        state = (
            stage,
            round(path[-1][0], 4),
            round(path[-1][1], 4),
        )
        if state in dead_states:
            return None

        # Every state first tries to finish directly.  Thus a one-elbow route
        # wins over every two-elbow route, and direct wins over both.
        finished = try_finish(path)
        if finished is not None:
            return finished

        if stage >= 2:
            dead_states.add(state)
            return None

        family = escape_waypoints if stage == 0 else approach_waypoints
        source = path[-1]
        for waypoint in family:
            if math.hypot(waypoint[0] - source[0], waypoint[1] - source[1]) < 1e-6:
                continue

            first = len(path) == 1
            cache_key = (
                round(source[0], 4), round(source[1], 4),
                round(waypoint[0], 4), round(waypoint[1], 4),
                first,
            )
            clear = prefix_cache.get(cache_key)
            if clear is None:
                clear = segment_clear(source, waypoint, first_segment=first)
                prefix_cache[cache_key] = clear
            if not clear:
                record_block(
                    "escape_blocked" if stage == 0 else "arc_blocked",
                    source, waypoint, first_segment=first,
                )
                continue

            partial = path + [waypoint]
            # Reject bad partial geometry immediately.  This is the essential
            # recursive pruning: do not construct the rest of a leader whose
            # prefix already violates rim or existing-leader geometry.
            if leader_hits_zodiac_rim(partial):
                continue
            if existing_paths and leaders_too_close(partial, existing_paths):
                if diagnostic is not None:
                    diagnostic["existing_leader_blocked"] = diagnostic.get(
                        "existing_leader_blocked", 0
                    ) + 1
                continue

            result = search(partial, stage + 1)
            if result is not None:
                return result

        dead_states.add(state)
        return None

    result = search([anchor], 0)
    if diagnostic is not None:
        diagnostic["recursive_nodes"] = diagnostic.get("recursive_nodes", 0) + nodes
        if result is None:
            diagnostic["route_failed"] = diagnostic.get("route_failed", 0) + 1
    return result
'''

new_text = text[:start] + "\n" + new_route.lstrip("\n")
P.write_text(new_text, encoding="utf-8")

me = Path(__file__)
source = me.read_text(encoding="utf-8")
needle = "\nENABLED = True\n"
if source.count(needle) != 1:
    raise SystemExit("Safety stop: ENABLED assignment not uniquely identifiable")
source = source.replace(needle, "\nENABLED = False\n", 1)
me.write_text(source, encoding="utf-8")

print(
    "Installed bounded recursive leader solver with local backtracking, "
    "memoized routing states, and a 2048-node safety cap; Repair Once is OFF."
)
