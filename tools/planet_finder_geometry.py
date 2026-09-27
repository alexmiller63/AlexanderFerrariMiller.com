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
DEFAULT_MAX_SEARCH_SECONDS = 180

# Bodies closer than this in ecliptic longitude form one deterministic
# near-conjunction group before any presentation-mode search begins.
NEAR_CONJUNCTION_DEGREES = 1.0

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
    """Return deterministic broad alignment groups after conjunction removal.

    Near-conjunction members are deliberately excluded: they belong to the
    earlier, more constrained placement phase and will already be frozen before
    alignment placement begins. Remaining connected circular-lambda neighbors
    within ``threshold`` form an alignment group.
    """
    conjunction_names = {
        item[1]
        for group in conjunction_groups(bodies)
        for item in group
    }
    remaining = [item for item in bodies if item[1] not in conjunction_names]
    return conjunction_groups(remaining, threshold=threshold)


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
    """Reject a proposed leader that grazes or crosses an existing leader."""
    return any(
        segments_too_close(path[i], path[i + 1], other[j], other[j + 1], clearance)
        for other in existing_paths
        for i in range(len(path) - 1)
        for j in range(len(other) - 1)
    )

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
    """Reject a leader that touches or crosses the inner zodiac rim.

    The inner chart is a convex disk, so a polyline remains clear of the
    circular rim exactly when every vertex remains inside the protected
    radius.  The body's anchor is at RI-5 and is therefore legal; elbows that
    wander out to the rim are not.
    """
    limit = RI - clearance
    return any(math.hypot(x - CX, y - CY) >= limit for x, y in path)


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
    """Yield each canonical label candidate once, cheapest geometry first.

    displacement_scale remains temporarily for API compatibility, but the
    complete lattice is always 0, +/-0.25, ... +/-2.00 label lengths.
    """
    theta = math.radians(180 + longitude)
    tx, ty = -math.sin(theta), -math.cos(theta)
    offered: list[tuple[float, float]] = []
    radii = (*PREFERRED_LABEL_RADII, *EXPANDED_LABEL_RADII)
    quarter_step = LABEL_LENGTH * 0.25
    for shell in range(9):
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
    for x, y in candidate_positions(longitude, displacement_scale):
        box = Box(x, y, w, h)
        reserved_hits = [i for i, obstacle in enumerate(reserved) if boxes_overlap(box, obstacle, LABEL_COLLISION_PADDING)]
        if reserved_hits:
            if diagnostic is not None:
                diagnostic["immutable_reserved"] = diagnostic.get("immutable_reserved", 0) + 1
                by_obstacle = diagnostic.setdefault("immutable_reserved_by_obstacle", {})
                for i in reserved_hits:
                    by_obstacle[i] = by_obstacle.get(i, 0) + 1
                diagnostic.setdefault("immutable_candidate_audit", []).append((x, y, "reserved", tuple(reserved_hits)))
            continue
        rim_limit = RI - LABEL_RIM_CLEARANCE
        if any(math.hypot(px - CX, py - CY) >= rim_limit for px in (box.left, box.right) for py in (box.top, box.bottom)):
            if diagnostic is not None:
                diagnostic["immutable_rim"] = diagnostic.get("immutable_rim", 0) + 1
                diagnostic.setdefault("immutable_candidate_audit", []).append((x, y, "rim", ()))
            continue
        yield x, y, box


def route(anchor: tuple[float, float], center: tuple[float, float], obstacles: list[Box], diagnostic=None, allow_initial_escape_count: int = 0, prefix_cache: dict | None = None, allow_initial_escape_indices: set[int] | None = None, target_box: Box | None = None, allow_angular_escape: bool = False) -> list[tuple[float, float]] | None:
    if prefix_cache is None:
        prefix_cache = {}
    # Ordinary callers keep the historical contiguous prefix behavior. Atomic
    # conjunctions may instead name exactly which local obstacles are escapable
    # on the first segment, so placed labels never become escapable by accident.
    if allow_initial_escape_indices is None:
        initial_escape_indices = set(range(allow_initial_escape_count))
    else:
        initial_escape_indices = set(allow_initial_escape_indices)

    def inside_escape_zone(point, box) -> bool:
        # Initial escape is allowed only when the leader actually starts inside
        # the protected footprint of an explicitly escapable reserved label.
        # This exception applies to the first segment only; all later segments
        # still treat the label as a hard obstacle.
        return (
            box.left - IMMUTABLE_LEADER_CLEARANCE <= point[0] <= box.right + IMMUTABLE_LEADER_CLEARANCE
            and box.top - IMMUTABLE_LEADER_CLEARANCE <= point[1] <= box.bottom + IMMUTABLE_LEADER_CLEARANCE
        )

    # A leader may not originate inside a non-escapable obstacle. Explicitly
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

    def target_landing(source, target):
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
        # Return the endpoint that can be rendered directly.  Back off 2 px
        # from the label boundary so the SVG round line cap cannot paint into
        # the label.  Rendering must not recalculate or clip this path later.
        hx, hy = hit[0] - source[0], hit[1] - source[1]
        distance = math.hypot(hx, hy)
        if distance <= 2.0 or distance < 1e-12:
            return source
        scale = (distance - 2.0) / distance
        return source[0] + hx * scale, source[1] + hy * scale

    def route_clear_of_target(path) -> bool:
        if target_box is None:
            return True
        if len(path) < 2:
            return False
        for i in range(len(path) - 2):
            if segment_hits_box(path[i], path[i + 1], target_box, IMMUTABLE_LEADER_CLEARANCE):
                return False
        return not segment_hits_box(path[-2], path[-1], target_box, -0.5)

    direct_endpoint = target_landing(anchor, target_box) if target_box is not None else center
    if direct_endpoint is not None and segment_clear(anchor, direct_endpoint, skip_start_escape=True):
        candidate = [anchor, direct_endpoint]
        if route_clear_of_target(candidate):
            return candidate
        if diagnostic is not None:
            diagnostic["target_approach"] = diagnostic.get("target_approach", 0) + 1
    elif diagnostic is not None:
        diagnostic["direct_blocked"] = diagnostic.get("direct_blocked", 0) + 1

    anchor_theta = math.atan2(anchor[1] - CY, anchor[0] - CX)
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
            final_endpoint = target_landing(elbow2, target_box) if target_box is not None else center
            if final_endpoint is None or not segment_clear(elbow2, final_endpoint):
                if diagnostic is not None:
                    diagnostic["final_blocked"] = diagnostic.get("final_blocked", 0) + 1
                continue
            candidate = [anchor, elbow1, elbow2, final_endpoint]
            if route_clear_of_target(candidate):
                return candidate
            if diagnostic is not None:
                diagnostic["target_approach"] = diagnostic.get("target_approach", 0) + 1
    return None
