"""Planet Finder geometry, labels, routing, and presentation support.

Extracted mechanically from generate_planet_finders.py. Keep this module
behavior-preserving; the generator remains the orchestration entry point.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto

from populate_ephemeris import TARGETS

W = H = 1400
CX = CY = 700
RO = 560
RI = 430
# Minimum visible separation between a rendered body label and the inner zodiac rim.
# This is hard geometry: proposals inside this protected annulus never enter DFS.
LABEL_RIM_CLEARANCE = 24
LABEL_COLLISION_PADDING = 14
IMMUTABLE_LEADER_CLEARANCE = 8
PLACED_LABEL_LEADER_CLEARANCE = 10
LEADER_TO_LEADER_CLEARANCE = 8.0
LEADER_RIM_CLEARANCE = 2.0
LABEL_LENGTH = 105.0
PREFERRED_LABEL_RADII = (345, 300, 255, 210, 390, 165, 120)
EXPANDED_LABEL_RADII = tuple(range(400, 79, -20))
ROUTE_RADII = (395, 365, 335, 305, 275, 245, 215, 185, 155)
SIGNS = [
    ("♈", "Aries"), ("♉", "Taurus"), ("♊", "Gemini"), ("♋", "Cancer"),
    ("♌", "Leo"), ("♍", "Virgo"), ("♎", "Libra"), ("♏", "Scorpio"),
    ("♐", "Sagittarius"), ("♑", "Capricorn"), ("♒", "Aquarius"), ("♓", "Pisces"),
]
BODY_SYMBOLS = {
    "sun": "☉", "moon": "☽", "mercury": "☿", "venus": "♀", "mars": "♂",
    "jupiter": "♃", "saturn": "♄", "ceres": "⚳", "uranus": "♅",
    "neptune": "♆", "pluto": "♇",
}
BODY_NAMES = {display.split(" ", 1)[1]: key for display, key, _ in TARGETS}
CANONICAL = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Ceres", "Uranus", "Neptune", "Pluto",
]

# Standalone defaults. GitHub Actions may override these through environment variables.
DEFAULT_CANDIDATE_LAYOUTS = 5
DEFAULT_MAX_NODE_CANDIDATES = 200
DEFAULT_MAX_SEARCH_SECONDS = 360

# Bodies closer than this in ecliptic longitude form one deterministic
# near-conjunction group before any presentation-mode search begins.
NEAR_CONJUNCTION_DEGREES = 0.1

# After conjunction members are frozen, remaining bodies within this angular
# neighborhood form broader alignment groups for the second placement phase.
ALIGNMENT_DEGREES = 30.0


def angular_separation_degrees(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def conjunction_groups(bodies, threshold: float = NEAR_CONJUNCTION_DEGREES):
    """Return deterministic near-conjunction groups in circular lambda order.

    Each input item is expected to be (key, name, longitude).  Connected
    neighbors within threshold belong to one group, including across 0/360.
    Only groups of two or more bodies are returned.  Members are ordered by
    increasing circular lambda from the group's first member.
    """
    items = sorted(bodies, key=lambda item: item[2] % 360.0)
    if len(items) < 2:
        return []

    gaps = [
        (items[(i + 1) % len(items)][2] - items[i][2]) % 360.0
        for i in range(len(items))
    ]
    breaks = [i for i, gap in enumerate(gaps) if gap > threshold]
    if not breaks:
        return [items]

    start = (breaks[0] + 1) % len(items)
    ordered = items[start:] + items[:start]
    groups = []
    current = [ordered[0]]
    for item in ordered[1:]:
        if angular_separation_degrees(current[-1][2], item[2]) <= threshold:
            current.append(item)
        else:
            if len(current) > 1:
                groups.append(current)
            current = [item]
    if len(current) > 1:
        groups.append(current)

    # Keep members of each conjunction in circular lambda order, but make the
    # list of independent conjunctions deterministic by the first member's
    # normalized longitude.  This prevents the arbitrary circular scan break
    # from rotating otherwise independent groups.
    groups.sort(key=lambda group: group[0][2] % 360.0)
    return groups


def alignment_groups(bodies, threshold: float = ALIGNMENT_DEGREES):
    """Return deterministic broad alignment groups.

    Conjunction status changes backtracking granularity only. It must never
    remove bodies from, split, or otherwise alter the ordinary coordinated
    alignment geometry. Therefore alignment grouping is computed directly
    from the complete body population at the alignment threshold.
    """
    return conjunction_groups(bodies, threshold=threshold)


class FinderMode(str, Enum):
    """Presentation modes for Planet Finder charts."""
    GREEK = "greek"
    LATIN = "latin"
    MIXED = "mixed"

    def __str__(self) -> str:
        return self.value


class Body(Enum):
    """Solar-System bodies participating in Planet Finder layout search."""
    SUN = auto()
    MOON = auto()
    MERCURY = auto()
    VENUS = auto()
    MARS = auto()
    JUPITER = auto()
    SATURN = auto()
    CERES = auto()
    URANUS = auto()
    NEPTUNE = auto()
    PLUTO = auto()

    @classmethod
    def from_name(cls, name: str) -> "Body":
        return cls[name.upper()]


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def left(self): return self.x - self.w / 2
    @property
    def right(self): return self.x + self.w / 2
    @property
    def top(self): return self.y - self.h / 2
    @property
    def bottom(self): return self.y + self.h / 2


def xy(longitude: float, radius: float) -> tuple[float, float]:
    theta = math.radians(180 + longitude)
    return CX + radius * math.cos(theta), CY - radius * math.sin(theta)


def boxes_overlap(a: Box, b: Box, pad: float = 0) -> bool:
    return not (
        a.right + pad <= b.left or b.right + pad <= a.left or
        a.bottom + pad <= b.top or b.bottom + pad <= a.top
    )


def segment_hits_box(a: tuple[float, float], b: tuple[float, float], box: Box, pad: float = 0) -> bool:
    """Return whether a line segment intersects a rectangle."""
    x0, y0 = a
    x1, y1 = b
    left, right = box.left - pad, box.right + pad
    top, bottom = box.top - pad, box.bottom + pad
    dx, dy = x1 - x0, y1 - y0
    p = (-dx, dx, -dy, dy)
    q = (x0 - left, right - x0, y0 - top, bottom - y0)
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if abs(pi) < 1e-12:
            if qi < 0:
                return False
            continue
        t = qi / pi
        if pi < 0:
            if t > u2:
                return False
            u1 = max(u1, t)
        else:
            if t < u1:
                return False
            u2 = min(u2, t)
    return True


def point_segment_distance(p, a, b) -> float:
    """Shortest distance from point p to line segment a-b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    q = (a[0] + t * dx, a[1] + t * dy)
    return math.hypot(p[0] - q[0], p[1] - q[1])


def segments_too_close(a, b, c, d, clearance: float = LEADER_TO_LEADER_CLEARANCE) -> bool:
    """Return whether two leader segments intersect or come within clearance."""
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if ((o1 > 0 and o2 < 0) or (o1 < 0 and o2 > 0)) and ((o3 > 0 and o4 < 0) or (o3 < 0 and o4 > 0)):
        return True
    return min(
        point_segment_distance(a, c, d),
        point_segment_distance(b, c, d),
        point_segment_distance(c, a, b),
        point_segment_distance(d, a, b),
    ) < clearance


def segment_distance(a, b, c, d):
    """Minimum Euclidean distance between two line segments."""
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if ((o1 > 0 and o2 < 0) or (o1 < 0 and o2 > 0)) and ((o3 > 0 and o4 < 0) or (o3 < 0 and o4 > 0)):
        return 0.0
    return min(
        point_segment_distance(a, c, d),
        point_segment_distance(b, c, d),
        point_segment_distance(c, a, b),
        point_segment_distance(d, a, b),
    )

def leaders_too_close(path, existing_paths, clearance: float = LEADER_TO_LEADER_CLEARANCE) -> bool:
    """Reject leader crossings/grazes after unavoidable close-anchor escape.

    Two astronomical anchors can legitimately be closer than the rendered
    leader clearance (or coincide in the conjunction limit).  Their leaders
    must be allowed to fan apart from that common neighborhood.  Once the
    corresponding first segments have escaped beyond the initial close-anchor
    condition, ordinary leader-to-leader clearance applies unchanged.
    """
    for other in existing_paths:
        close_anchors = math.hypot(path[0][0] - other[0][0], path[0][1] - other[0][1]) < clearance
        for i in range(len(path) - 1):
            for j in range(len(other) - 1):
                if close_anchors and i == 0 and j == 0:
                    # Shared/nearby origins are imposed by the sky geometry.
                    # Do not mistake that unavoidable initial proximity for a
                    # layout collision; all later segment pairs remain strict.
                    continue
                if segments_too_close(path[i], path[i + 1], other[j], other[j + 1], clearance):
                    return True
    return False

def minimum_leader_separation(path, existing_paths):
    """Return the minimum segment-to-segment distance to existing leaders."""
    best = math.inf
    best_pair = None
    for oi, other in enumerate(existing_paths):
        for i in range(len(path) - 1):
            for j in range(len(other) - 1):
                d = segment_distance(path[i], path[i + 1], other[j], other[j + 1])
                if d < best:
                    best = d
                    best_pair = (oi, i, j)
    return best, best_pair


def leader_hits_zodiac_rim(path, clearance: float = LEADER_RIM_CLEARANCE) -> bool:
    """Reject a leader that returns to/crosses the protected zodiac rim.

    Body anchors intentionally start near the inner zodiac rim and may lie
    inside its clearance band.  Permit that contiguous initial band only while
    the leader escapes inward.  After the path first reaches the protected
    interior, it may never leave it again.  Because the protected interior is
    a convex disk, endpoints inside it imply the whole intervening segment is
    inside it as well.
    """
    limit = RI - clearance
    radii = [math.hypot(x - CX, y - CY) for x, y in path]
    entered_interior = False
    previous_radius = None
    for radius in radii:
        if radius < limit:
            entered_interior = True
        elif entered_interior:
            return True
        elif previous_radius is not None and radius > previous_radius + 1e-9:
            # Before entering the protected interior, the initial escape must
            # move monotonically inward rather than wander outward along/rimward.
            return True
        previous_radius = radius
    return False


def label_size(mode: str, name: str) -> tuple[float, float]:
    if mode == "greek":
        return 64, 64
    if mode == "latin":
        return max(104, 13 * len(name) + 28), 50
    return max(132, 13 * len(name) + 68), 50


def reserved_boxes(mode: str) -> list[Box]:
    """Hard obstacles matching the geometry actually rendered on the chart.

    These boxes are consulted at proposal time, before a body-label position
    can enter the DFS candidate set.  Keep them deliberately conservative:
    rendered text must fit *inside* its obstacle, never merely approximate it.
    """
    boxes = [Box(CX, 682, 520, 40), Box(CX, 722, 690, 34), Box(CX, 757, 440, 34)]
    for i, (_, name) in enumerate(SIGNS):
        x, y = xy(i * 30 + 15, (RI + RO) / 2)
        if mode == "greek":
            boxes.append(Box(x, y, 76, 76))
        elif mode == "latin":
            boxes.append(Box(x, y, max(62, 13 * len(name) + 12), 36))
        else:
            boxes.append(Box(x, y, max(78, 12 * len(name) + 38), 34))
    return boxes


def candidate_positions(longitude: float, displacement_scale: float = 2.0):
    """Yield each canonical label candidate once, widest geometry first.

    The complete lattice is +/-2.00, +/-1.75, ... +/-0.25, then 0 label
    lengths.  This preserves the full candidate set while honoring the Planet
    Finder strategy: try maximum separation before progressively narrowing.
    displacement_scale remains temporarily for API compatibility.
    """
    theta = math.radians(180 + longitude)
    tx, ty = -math.sin(theta), -math.cos(theta)
    offered: list[tuple[float, float]] = []
    radii = (*PREFERRED_LABEL_RADII, *EXPANDED_LABEL_RADII)
    quarter_step = LABEL_LENGTH * 0.25
    for shell in range(8, -1, -1):
        shifts = (0.0,) if shell == 0 else (-shell * quarter_step, shell * quarter_step)
        for shift in shifts:
            for r in radii:
                bx, by = xy(longitude, r)
                x, y = bx + shift * tx, by + shift * ty
                if any(math.hypot(x - ox, y - oy) < 1e-9 for ox, oy in offered):
                    continue
                offered.append((x, y))
                yield x, y

def legal_candidate_positions(longitude: float, w: float, h: float, reserved: list[Box], displacement_scale: float = 2.0, diagnostic: dict | None = None):
    # Diagnostic only: for the Venus/Sun ladder, capture the first canonical
    # candidate before immutable filtering and its exact fate.  At 2deg the
    # Sun's first candidate survives; at 1deg it disappears from the legal
    # pool.  This trace identifies the rejecting immutable constraint without
    # changing candidate generation, legality, or ordering.
    trace_first = diagnostic is not None and abs(longitude - 101.0) < 1e-9
    first = True
    for x, y in candidate_positions(longitude, displacement_scale):
        box = Box(x, y, w, h)
        reserved_hits = [i for i, obstacle in enumerate(reserved) if boxes_overlap(box, obstacle, LABEL_COLLISION_PADDING)]
        if reserved_hits:
            if trace_first and first:
                diagnostic["sun_1deg_first_candidate_trace"] = {
                    "x": x, "y": y, "w": w, "h": h,
                    "result": "reserved", "reserved_hits": tuple(reserved_hits),
                    "corner_radii": tuple(
                        math.hypot(px - CX, py - CY)
                        for px in (box.left, box.right)
                        for py in (box.top, box.bottom)
                    ),
                }
            if diagnostic is not None:
                diagnostic["immutable_reserved"] = diagnostic.get("immutable_reserved", 0) + 1
                by_obstacle = diagnostic.setdefault("immutable_reserved_by_obstacle", {})
                for i in reserved_hits:
                    by_obstacle[i] = by_obstacle.get(i, 0) + 1
                diagnostic.setdefault("immutable_candidate_audit", []).append((x, y, "reserved", tuple(reserved_hits)))
            first = False
            continue
        rim_limit = RI - LABEL_RIM_CLEARANCE
        corner_radii = tuple(
            math.hypot(px - CX, py - CY)
            for px in (box.left, box.right)
            for py in (box.top, box.bottom)
        )
        if any(radius >= rim_limit for radius in corner_radii):
            if trace_first and first:
                diagnostic["sun_1deg_first_candidate_trace"] = {
                    "x": x, "y": y, "w": w, "h": h,
                    "result": "rim", "rim_limit": rim_limit,
                    "corner_radii": corner_radii,
                }
            if diagnostic is not None:
                diagnostic["immutable_rim"] = diagnostic.get("immutable_rim", 0) + 1
                diagnostic.setdefault("immutable_candidate_audit", []).append((x, y, "rim", ()))
            first = False
            continue
        if trace_first and first:
            diagnostic["sun_1deg_first_candidate_trace"] = {
                "x": x, "y": y, "w": w, "h": h,
                "result": "legal", "rim_limit": rim_limit,
                "corner_radii": corner_radii,
            }
        first = False
        yield x, y, box


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
                # Exact cheap reject before the comparatively expensive
                # segment-distance calculation.  If the two segment AABBs are
                # separated by at least the required leader clearance on
                # either axis, their Euclidean separation cannot violate the
                # clearance.  This is geometry-preserving: only provably
                # distant segment pairs are skipped.
                clearance = LEADER_TO_LEADER_CLEARANCE
                if (
                    max(a[0], b[0]) + clearance <= min(c[0], d[0])
                    or max(c[0], d[0]) + clearance <= min(a[0], b[0])
                    or max(a[1], b[1]) + clearance <= min(c[1], d[1])
                    or max(c[1], d[1]) + clearance <= min(a[1], b[1])
                ):
                    continue
                dist = segment_distance(a, b, c, d)
                if dist >= clearance:
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
    deepest_route_depth = 0
    dead = set()
    if diagnostic is not None:
        diagnostic["route_calls"] = diagnostic.get("route_calls", 0) + 1

    def partial_legal(path):
        if leader_hits_zodiac_rim(path):
            return False
        if existing_paths and leaders_too_close(path, existing_paths):
            return False
        return True

    def solve(path, depth):
        nonlocal nodes, deepest_route_depth
        nodes += 1
        deepest_route_depth = max(deepest_route_depth, depth)
        if nodes > node_cap:
            if diagnostic is not None:
                diagnostic["node_cap_hits"] = diagnostic.get("node_cap_hits", 0) + 1
            return None
        if depth > max_depth:
            if diagnostic is not None:
                diagnostic["depth_cap_hits"] = diagnostic.get("depth_cap_hits", 0) + 1
            return None
        source = path[-1]
        landing = target_landing(source)
        if landing is None:
            if diagnostic is not None:
                diagnostic["landing_failed"] = diagnostic.get("landing_failed", 0) + 1
            return None

        state = (round(source[0], 3), round(source[1], 3), depth)
        if state in dead:
            if diagnostic is not None:
                diagnostic["dead_state_hits"] = diagnostic.get("dead_state_hits", 0) + 1
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
            detail_key = "directed_box_by_index" if blocker[1] == "box" else "directed_leader_by_index"
            detail = diagnostic.setdefault(detail_key, {})
            blocker_index = blocker[2] if blocker[1] == "box" else blocker[2][0]
            detail[blocker_index] = detail.get(blocker_index, 0) + 1

        for waypoint in bypass_points(source, landing, blocker):
            # The segment to the bypass itself must be legal; if it has another
            # blocker, recurse toward the bypass by treating it as the next
            # local destination would recreate a general maze search. Instead
            # prune it and try the opposite side; subsequent recursion resumes
            # aiming at the real label.
            if first_blocker(source, waypoint, len(path) == 1) is not None:
                if diagnostic is not None:
                    diagnostic["bypass_blocked"] = diagnostic.get("bypass_blocked", 0) + 1
                continue
            partial = path + [waypoint]
            if not partial_legal(partial):
                if diagnostic is not None:
                    diagnostic["bypass_illegal"] = diagnostic.get("bypass_illegal", 0) + 1
                continue
            result = solve(partial, depth + 1)
            if result is not None:
                return result

        dead.add(state)
        return None

    result = solve([anchor], 0)
    if diagnostic is not None:
        diagnostic["recursive_nodes"] = diagnostic.get("recursive_nodes", 0) + nodes
        diagnostic["max_recursive_nodes"] = max(diagnostic.get("max_recursive_nodes", 0), nodes)
        diagnostic["max_route_depth"] = max(diagnostic.get("max_route_depth", 0), deepest_route_depth)
        if result is None:
            diagnostic["route_failed"] = diagnostic.get("route_failed", 0) + 1
        else:
            diagnostic["route_succeeded"] = diagnostic.get("route_succeeded", 0) + 1
    return result
