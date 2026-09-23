"""Geometry primitives and routing for the Planet Finder generator."""
from __future__ import annotations

import math
from dataclasses import dataclass

W = H = 1400
CX = CY = 700
RO = 560
RI = 430
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


def leaders_too_close(path, existing_paths, clearance: float = LEADER_TO_LEADER_CLEARANCE) -> bool:
    """Reject a proposed leader that grazes or crosses an existing leader."""
    return any(
        segments_too_close(path[i], path[i + 1], other[j], other[j + 1], clearance)
        for other in existing_paths
        for i in range(len(path) - 1)
        for j in range(len(other) - 1)
    )


def leader_hits_zodiac_rim(path, clearance: float = LEADER_RIM_CLEARANCE) -> bool:
    """Reject a leader that touches or crosses the inner zodiac rim."""
    limit = RI - clearance
    return any(math.hypot(x - CX, y - CY) >= limit for x, y in path)


def label_size(mode: str, name: str) -> tuple[float, float]:
    if mode == "greek":
        return 64, 64
    if mode == "latin":
        return max(104, 13 * len(name) + 28), 50
    return max(132, 13 * len(name) + 68), 50


def reserved_boxes(mode: str) -> list[Box]:
    """Hard obstacles matching the geometry actually rendered on the chart."""
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
    """Yield deterministic geometric proposals from coarse to fine."""
    theta = math.radians(180 + longitude)
    tx, ty = -math.sin(theta), -math.cos(theta)
    offered: list[tuple[float, float]] = []

    def offer(radii, shifts):
        for r in radii:
            bx, by = xy(longitude, r)
            for shift in shifts:
                x, y = bx + shift * tx, by + shift * ty
                if any(math.hypot(x - ox, y - oy) < 1e-9 for ox, oy in offered):
                    continue
                offered.append((x, y))
                yield x, y

    yield from offer(PREFERRED_LABEL_RADII, (0.0,))
    shift = LABEL_LENGTH * displacement_scale
    yield from offer(PREFERRED_LABEL_RADII, (-shift, shift))
    yield from offer(EXPANDED_LABEL_RADII, (0.0,))
    yield from offer(EXPANDED_LABEL_RADII, (-shift, shift))


def legal_candidate_positions(longitude: float, w: float, h: float, reserved: list[Box], displacement_scale: float = 2.0, diagnostic: dict | None = None):
    """Yield only proposals that are legal against immutable chart geometry."""
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


def route(anchor: tuple[float, float], center: tuple[float, float], obstacles: list[Box], diagnostic=None, allow_initial_escape_count: int = 0, prefix_cache: dict | None = None) -> list[tuple[float, float]] | None:
    """Prefer a straight leader; otherwise try deterministic radial elbows."""
    def hits(a, b, obstacle, allow_initial_escape=False, pad=8):
        inside = obstacle.left - pad <= a[0] <= obstacle.right + pad and obstacle.top - pad <= a[1] <= obstacle.bottom + pad
        if not inside:
            return segment_hits_box(a, b, obstacle, pad)
        if not allow_initial_escape:
            return True
        dx, dy = b[0] - a[0], b[1] - a[1]
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            return False
        ts = []
        if abs(dx) >= 1e-12:
            ts.extend([(obstacle.left - pad - a[0]) / dx, (obstacle.right + pad - a[0]) / dx])
        if abs(dy) >= 1e-12:
            ts.extend([(obstacle.top - pad - a[1]) / dy, (obstacle.bottom + pad - a[1]) / dy])
        exits = []
        for t in ts:
            if 0 < t < 1:
                p = (a[0] + dx * (t + 1e-7), a[1] + dy * (t + 1e-7))
                if not (obstacle.left - pad <= p[0] <= obstacle.right + pad and obstacle.top - pad <= p[1] <= obstacle.bottom + pad):
                    exits.append(t)
        if not exits:
            return False
        t = min(exits) + 1e-6
        escaped = (a[0] + dx * t, a[1] + dy * t)
        return segment_hits_box(escaped, b, obstacle, pad)

    def obstacle_pad(i: int) -> int:
        return IMMUTABLE_LEADER_CLEARANCE if i < allow_initial_escape_count else PLACED_LABEL_LEADER_CLEARANCE

    straight_blockers = [i for i, b in enumerate(obstacles) if hits(anchor, center, b, allow_initial_escape=(i < allow_initial_escape_count), pad=obstacle_pad(i))]
    if not straight_blockers:
        return [anchor, center]
    if diagnostic is not None:
        diagnostic["straight_blocked"] = diagnostic.get("straight_blocked", 0) + 1
        for i in straight_blockers:
            key = f"obstacle_{i}"
            blockers = diagnostic.setdefault("straight_blockers", {})
            blockers[key] = blockers.get(key, 0) + 1

    for i, obstacle in enumerate(obstacles):
        if i < allow_initial_escape_count:
            continue
        pad = obstacle_pad(i)
        if obstacle.left - pad <= anchor[0] <= obstacle.right + pad and obstacle.top - pad <= anchor[1] <= obstacle.bottom + pad:
            if diagnostic is not None:
                diagnostic["anchor_blocked"] = diagnostic.get("anchor_blocked", 0) + 1
                diagnostic["route_failed"] = diagnostic.get("route_failed", 0) + 1
            return None

    ax, ay = anchor
    for r in ROUTE_RADII:
        lon = math.degrees(math.atan2(-(ay - CY), ax - CX)) - 180
        ex, ey = xy(lon, r)
        first_blockers = [i for i, b in enumerate(obstacles) if hits(anchor, (ex, ey), b, allow_initial_escape=(i < allow_initial_escape_count), pad=obstacle_pad(i))]
        second_blockers = [i for i, b in enumerate(obstacles) if hits((ex, ey), center, b, pad=obstacle_pad(i))]
        if not first_blockers and not second_blockers:
            return [anchor, (ex, ey), center]
        if diagnostic is not None:
            elbow = diagnostic["elbows"].setdefault(r, {"first": {}, "second": {}})
            for i in first_blockers:
                key = f"obstacle_{i}"
                elbow["first"][key] = elbow["first"].get(key, 0) + 1
            for i in second_blockers:
                key = f"obstacle_{i}"
                elbow["second"][key] = elbow["second"].get(key, 0) + 1

    lon = math.degrees(math.atan2(-(ay - CY), ax - CX)) - 180
    theta = math.radians(180 + lon)
    tx, ty = -math.sin(theta), -math.cos(theta)
    cache_key = "dogleg_prefixes"
    dogleg_prefixes = prefix_cache.get(cache_key) if prefix_cache is not None else None
    if dogleg_prefixes is None:
        dogleg_prefixes = []
        for r in ROUTE_RADII:
            e1 = xy(lon, r)
            first_blocked = any(hits(anchor, e1, b, allow_initial_escape=(i < allow_initial_escape_count), pad=obstacle_pad(i)) for i, b in enumerate(obstacles))
            if first_blocked:
                continue
            for shift in (70, -70, 105, -105, 140, -140, 175, -175, 210, -210, 245, -245, 280, -280, 315, -315):
                e2 = (e1[0] + shift * tx, e1[1] + shift * ty)
                second_blocked = any(hits(e1, e2, b, pad=obstacle_pad(i)) for i, b in enumerate(obstacles))
                if not second_blocked:
                    dogleg_prefixes.append((e1, e2))
        if prefix_cache is not None:
            prefix_cache[cache_key] = dogleg_prefixes

    for e1, e2 in dogleg_prefixes:
        third_blocked = any(hits(e2, center, b, pad=obstacle_pad(i)) for i, b in enumerate(obstacles))
        if not third_blocked:
            if diagnostic is not None:
                diagnostic["dogleg_success"] = diagnostic.get("dogleg_success", 0) + 1
            return [anchor, e1, e2, center]
    if diagnostic is not None:
        diagnostic["dogleg_failed"] = diagnostic.get("dogleg_failed", 0) + 1
        diagnostic["route_failed"] = diagnostic.get("route_failed", 0) + 1
    return None
