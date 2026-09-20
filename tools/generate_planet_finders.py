#!/usr/bin/env python3
"""Generate canonical weekly Planet Finder SVGs from Star Almanack calculations.

The renderer follows the frozen Planet Finder specification. It consumes the
same internally calculated planetary positions as the weekly ephemeris and does
not query Horizons or another answer service.
"""
from __future__ import annotations

import argparse
import html
import math
import os
import time
from dataclasses import dataclass
from datetime import date
from enum import Enum, auto
from pathlib import Path

from populate_ephemeris import TARGETS, computed_ephemeris, week_count
from star_almanack_ephemeris import StarAlmanackEphemeris

ROOT = Path(__file__).resolve().parents[1]
W = H = 1400
CX = CY = 700
RO = 560
RI = 430
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


def segments_too_close(a, b, c, d, clearance: float = 8.0) -> bool:
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


def leaders_too_close(path, existing_paths, clearance: float = 8.0) -> bool:
    """Reject a proposed leader that grazes or crosses an existing leader."""
    return any(
        segments_too_close(path[i], path[i + 1], other[j], other[j + 1], clearance)
        for other in existing_paths
        for i in range(len(path) - 1)
        for j in range(len(other) - 1)
    )


def leader_hits_zodiac_rim(path, clearance: float = 2.0) -> bool:
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
            # 48 px zodiac glyphs need more than their nominal em box once
            # font bearings/antialiasing are included.
            boxes.append(Box(x, y, 76, 76))
        elif mode == "latin":
            # Rendered at 24 px Georgia.  Approximate the visible text envelope
            # from the font size rather than inflating it to a large minimum.
            boxes.append(Box(x, y, max(62, 13 * len(name) + 12), 36))
        else:
            # Mixed mode renders "<glyph> <name>" at 22 px.  The obstacle should
            # follow that visible label, not an oversized invisible rectangle.
            # Allow about one em for the glyph/space plus Georgia's average
            # lowercase advance for the Latin name.
            boxes.append(Box(x, y, max(78, 12 * len(name) + 38), 34))
    return boxes


def candidate_positions(longitude: float, displacement_scale: float = 2.0):
    """Yield deterministic geometric proposals from coarse to fine.

    Candidate ordering is geometry only. DFS owns all backtracking and the
    viability rules decide whether each proposal is legal. Explore every
    position at a large displacement before introducing closer siblings.
    """
    preferred_radii = (345, 300, 255, 210, 390, 165, 120)
    theta = math.radians(180 + longitude)
    tx, ty = -math.sin(theta), -math.cos(theta)

    # One label-length is the established 105 px tangential placement step.
    # Search coarse-to-fine: exhaust all siblings at each displacement before
    # allowing recursion to consider a smaller movement.
    label_length = 105.0
    offered: list[tuple[float, float]] = []

    def offer(radii, shifts):
        for r in radii:
            bx, by = xy(longitude, r)
            for shift in shifts:
                x, y = bx + shift * tx, by + shift * ty
                if any(
                    math.hypot(x - ox, y - oy) < 1e-9
                    for ox, oy in offered
                ):
                    continue
                offered.append((x, y))
                yield x, y

    # Preserve the natural position first, then explore increasingly finer
    # displacement rings. Within a ring, both tangential directions are peers.
    yield from offer(preferred_radii, (0.0,))
    shift = label_length * displacement_scale
    yield from offer(preferred_radii, (-shift, shift))

    expanded_radii = tuple(range(400, 79, -20))
    yield from offer(expanded_radii, (0.0,))
    yield from offer(expanded_radii, (-shift, shift))


def legal_candidate_positions(
    longitude: float,
    w: float,
    h: float,
    reserved: list[Box],
    displacement_scale: float = 2.0,
    diagnostic: dict | None = None,
):
    """Yield only proposals that are legal against immutable chart geometry.

    When diagnostic is supplied, rejected raw proposals are classified here so
    terminal search output can distinguish immutable-geometry impossibility
    from DFS interactions between movable labels/leaders.
    """
    for x, y in candidate_positions(longitude, displacement_scale):
        box = Box(x, y, w, h)
        reserved_hits = [
            i for i, obstacle in enumerate(reserved)
            if boxes_overlap(box, obstacle, 14)
        ]
        if reserved_hits:
            if diagnostic is not None:
                diagnostic["immutable_reserved"] = diagnostic.get("immutable_reserved", 0) + 1
                by_obstacle = diagnostic.setdefault("immutable_reserved_by_obstacle", {})
                for i in reserved_hits:
                    by_obstacle[i] = by_obstacle.get(i, 0) + 1
            continue
        # Body labels live inside the inner zodiac rim.  A label touching or
        # crossing that border is rotten geometry, not a scoring preference.
        # Test all 4 corners with clearance before the proposal can enter DFS.
        rim_limit = RI - 14
        if any(
            math.hypot(px - CX, py - CY) >= rim_limit
            for px in (box.left, box.right)
            for py in (box.top, box.bottom)
        ):
            if diagnostic is not None:
                diagnostic["immutable_rim"] = diagnostic.get("immutable_rim", 0) + 1
            continue
        yield x, y, box


def route(
    anchor: tuple[float, float],
    center: tuple[float, float],
    obstacles: list[Box],
    diagnostic=None,
    allow_initial_escape_count: int = 0,
    prefix_cache: dict | None = None,
) -> list[tuple[float, float]] | None:
    """Prefer a straight leader; otherwise try deterministic radial elbows.

    A leader is allowed to leave an obstacle that contains its anchor.  This
    is the correct geometry for a body marker lying beneath/adjacent to a
    zodiac label: the leader may escape that local label, but after it has
    exited it may not cross that obstacle again.
    """
    def hits(a, b, obstacle, allow_initial_escape=False, pad=8):
        # Only an immutable chart obstacle containing the body's anchor may
        # permit the initial escape. A placed label belonging to another body
        # must never become an escape obstacle merely because this body's
        # anchor happens to fall inside it. The final validator enforces the
        # same rule; route generation must agree with it.
        inside = (
            obstacle.left - pad <= a[0] <= obstacle.right + pad and
            obstacle.top - pad <= a[1] <= obstacle.bottom + pad
        )
        if not inside:
            return segment_hits_box(a, b, obstacle, pad)
        # Starting inside an obstacle is legal only for the explicitly
        # permitted immutable obstacle containing the body's own anchor.
        # A placed body label is never an escape obstacle: if the anchor is
        # already inside another body's label, this route is rotten before
        # routing begins and must be rejected immediately.
        if not allow_initial_escape:
            return True
        dx, dy = b[0] - a[0], b[1] - a[1]
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            return False
        ts = []
        if abs(dx) >= 1e-12:
            ts.extend([
                (obstacle.left - pad - a[0]) / dx,
                (obstacle.right + pad - a[0]) / dx,
            ])
        if abs(dy) >= 1e-12:
            ts.extend([
                (obstacle.top - pad - a[1]) / dy,
                (obstacle.bottom + pad - a[1]) / dy,
            ])
        exits = []
        for t in ts:
            if 0 < t < 1:
                p = (a[0] + dx * (t + 1e-7), a[1] + dy * (t + 1e-7))
                if not (
                    obstacle.left - pad <= p[0] <= obstacle.right + pad and
                    obstacle.top - pad <= p[1] <= obstacle.bottom + pad
                ):
                    exits.append(t)
        if not exits:
            return False
        t = min(exits) + 1e-6
        escaped = (a[0] + dx * t, a[1] + dy * t)
        return segment_hits_box(escaped, b, obstacle, pad)

    def obstacle_pad(i: int) -> int:
        # Match final validation exactly: immutable chart obstacles use 8 px
        # clearance; placed body labels use 10 px. Candidate admission must
        # never be more permissive than final validation.
        return 8 if i < allow_initial_escape_count else 10

    straight_blockers = [
        i for i, b in enumerate(obstacles)
        if hits(
            anchor,
            center,
            b,
            allow_initial_escape=(i < allow_initial_escape_count),
            pad=obstacle_pad(i),
        )    ]
    if not straight_blockers:
        return [anchor, center]
    if diagnostic is not None:
        diagnostic["straight_blocked"] = diagnostic.get("straight_blocked", 0) + 1
        for i in straight_blockers:
            key = f"obstacle_{i}"
            blockers = diagnostic.setdefault("straight_blockers", {})
            blockers[key] = blockers.get(key, 0) + 1

    # Rotten-cake preflight: a placed body label containing this body's
    # anchor is an immutable dead end for the current DFS state. No straight,
    # elbow, or dogleg route may legally escape another body's label, so reject
    # the candidate before entering the expensive route-shape search.
    for i, obstacle in enumerate(obstacles):
        if i < allow_initial_escape_count:
            continue
        pad = obstacle_pad(i)
        if (
            obstacle.left - pad <= anchor[0] <= obstacle.right + pad and
            obstacle.top - pad <= anchor[1] <= obstacle.bottom + pad
        ):
            if diagnostic is not None:
                diagnostic["anchor_blocked"] = diagnostic.get("anchor_blocked", 0) + 1
                diagnostic["route_failed"] = diagnostic.get("route_failed", 0) + 1
            return None

    ax, ay = anchor
    for r in (395, 365, 335, 305, 275, 245, 215, 185, 155):
        lon = math.degrees(math.atan2(-(ay - CY), ax - CX)) - 180
        ex, ey = xy(lon, r)
        first_blockers = [
            i for i, b in enumerate(obstacles)
            if hits(
                anchor,
                (ex, ey),
                b,
                allow_initial_escape=(i < allow_initial_escape_count),
                pad=obstacle_pad(i),
            )
        ]
        second_blockers = [
            i for i, b in enumerate(obstacles)
            if hits((ex, ey), center, b, pad=obstacle_pad(i))
        ]
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

    # A single radial elbow can still force the final leg through the wide
    # center annotations.  Try deterministic two-elbow doglegs next: leave
    # the body radially, move tangentially around the center text, then enter
    # the label.  Straight and one-elbow routes remain preferred.
    lon = math.degrees(math.atan2(-(ay - CY), ax - CX)) - 180
    theta = math.radians(180 + lon)
    tx, ty = -math.sin(theta), -math.cos(theta)
    # The first 2 dogleg legs depend only on the body's anchor and the
    # current DFS obstacle state, not on the candidate label position. Build
    # those legal prefixes once for this frame and reuse them for every label
    # candidate; only the final e2->label leg is candidate-specific.
    cache_key = "dogleg_prefixes"
    dogleg_prefixes = prefix_cache.get(cache_key) if prefix_cache is not None else None
    if dogleg_prefixes is None:
        dogleg_prefixes = []
        for r in (395, 365, 335, 305, 275, 245, 215, 185, 155):
            e1 = xy(lon, r)
            first_blocked = any(
                hits(
                    anchor,
                    e1,
                    b,
                    allow_initial_escape=(i < allow_initial_escape_count),
                    pad=obstacle_pad(i),
                )
                for i, b in enumerate(obstacles)
            )
            if first_blocked:
                continue
            for shift in (70, -70, 105, -105, 140, -140, 175, -175, 210, -210, 245, -245, 280, -280, 315, -315):
                e2 = (e1[0] + shift * tx, e1[1] + shift * ty)
                second_blocked = any(
                    hits(e1, e2, b, pad=obstacle_pad(i))
                    for i, b in enumerate(obstacles)
                )
                if not second_blocked:
                    dogleg_prefixes.append((e1, e2))
        if prefix_cache is not None:
            prefix_cache[cache_key] = dogleg_prefixes

    for e1, e2 in dogleg_prefixes:
        third_blocked = any(
            hits(e2, center, b, pad=obstacle_pad(i))
            for i, b in enumerate(obstacles)
        )
        if not third_blocked:
            if diagnostic is not None:
                diagnostic["dogleg_success"] = diagnostic.get("dogleg_success", 0) + 1
            return [anchor, e1, e2, center]
    if diagnostic is not None:
        diagnostic["dogleg_failed"] = diagnostic.get("dogleg_failed", 0) + 1
        diagnostic["route_failed"] = diagnostic.get("route_failed", 0) + 1
    return None




@dataclass(frozen=True)
class SearchOutcome:
    """Result of one fixed-order DFS attempt."""
    kind: str
    solutions: list
    contest_keys: list
    blocker: str | None = None
    rejection_stats: dict | None = None


class DepthNodeBudgetExhausted(RuntimeError):
    """Signal that a body-depth node budget is exhausted for this DFS tree."""

    def __init__(self, depth: int, name: str):
        super().__init__(f"node budget exhausted at depth {depth} for {name}")
        self.depth = depth
        self.name = name


def _solve_order(mode: str, bodies, order, budget, target_solutions=5, order_index=1, total_orders=None, context_label=None, displacement_scale=2.0):
    """Solve one fixed body ordering with recursive depth-first search.

    The ordering is fixed for this pass. Each recursive call owns one body
    depth; returning from a child restores the parent placement and tries the
    next sibling. When the ordering is exhausted, the caller selects a
    deliberately distant ordering.
    """
    reserved = reserved_boxes(mode)
    reserved_names = ["center_title", "center_direction", "center_sector_note",
                      *[f"zodiac_{name}" for _, name in SIGNS]]
    placed: list[Box] = []
    leaders: list[list[tuple[float, float]]] = []
    staged = {}
    nodes = 0
    started = time.monotonic()
    last_heartbeat = started
    candidates = 0
    rejected_overlap = 0
    rejected_leader = 0
    rejected_route = 0
    backtracks = 0
    deepest = 0
    # Diagnostic-only DFS residence accounting. Charge elapsed controller time
    # to the depth/body that owned control between loop iterations; this shows
    # which descendant subtree consumes a parent's generator suspension time.
    depth_residence = {}
    depth_visits = {}
    # Count repeated zero-candidate visits across different parent states.
    # This is the second squeaky-wheel failure mode: a body can repeatedly
    # block the tree without any one prefix reaching its candidate cap.
    dead_end_visits = {}
    # Explosion accounting is per body for this entire fixed ordering. A body
    # that consumes the cap across multiple DFS prefixes is the squeaky wheel;
    # layout() then discards this ordering, promotes that body, and starts fresh.
    body_attempts = {name: 0 for _, (_, name, _) in order}
    diagnostic_stats = {}
    route_diagnostics = {}
    solutions = []
    solution_keys = set()
    contest_keys = []
    current_body = "-"
    exhausted = False
    def dump_diagnostics(reason):
        order_names = " > ".join(item[1][1] for item in order)
        print(
            f"Planet Finder {mode}: TERMINAL {context_label + ' ' if context_label else ''}reason={reason} order={order_index}"
            f"{('/' + str(total_orders)) if total_orders else ''} "
            f"nodes={nodes:,} deepest={deepest}/{len(order)} current_body={current_body} "
            f"candidates={candidates:,} rejects[overlap={rejected_overlap:,},"
            f"leader={rejected_leader:,},route={rejected_route:,}] "
            f"backtracks={backtracks:,}",
            flush=True,
        )
        print(f"Planet Finder {mode}: TERMINAL ORDER sequence={order_names}", flush=True)
        for (depth, name), s in sorted(diagnostic_stats.items()):
            immutable_names = {
                reserved_names[i] if i < len(reserved_names) else str(i): count
                for i, count in sorted(s.get("immutable_reserved_by_obstacle", {}).items())
            }
            print(
                f"Planet Finder {mode}: TERMINAL BODY depth={depth}/{len(order)} body={name} "
                f"status={'evaluated' if s.get('started') else ('blocked-' + s['blocked'] if s.get('blocked') else 'not-evaluated')} "
                f"generated={s['generated']:,} viable={s['viable']:,} "
                f"rejects[immutable-reserved={s.get('immutable_reserved', 0):,},"
                f"immutable-rim={s.get('immutable_rim', 0):,},"
                f"placed-overlap={s['overlap']:,},"
                f"existing-leader={s.get('leader_existing', 0):,},"
                f"route={s['route']:,},"
                f"leader-rim={s.get('leader_rim', 0):,},"
                f"leader-graze={s.get('leader_graze', 0):,}] "
                f"immutable-obstacles={immutable_names}",
                flush=True,
            )
        for depth in sorted(set(depth_residence) | set(depth_visits)):
            body_name = order[depth][1][1] if depth < len(order) else "complete-layout"
            print(
                f"Planet Finder {mode}: TERMINAL DFS-TIME depth={depth}/{len(order)} "
                f"body={body_name} residence={depth_residence.get(depth, 0.0):.3f}s "
                f"visits={depth_visits.get(depth, 0):,}",
                flush=True,
            )
        for (depth, name), r in sorted(route_diagnostics.items()):
            blockers = r.get("straight_blockers", {})
            obstacle_names = r.get("obstacle_names", [])
            named_blockers = {
                (obstacle_names[int(key.split("_", 1)[1])] if key.startswith("obstacle_") and int(key.split("_", 1)[1]) < len(obstacle_names) else key): count
                for key, count in blockers.items()
            }
            print(
                f"Planet Finder {mode}: TERMINAL ROUTE depth={depth}/{len(order)} body={name} "
                f"straight_blocked={r.get('straight_blocked', 0):,} "
                f"route_failed={r.get('route_failed', 0):,} "
                f"anchor_blocked={r.get('anchor_blocked', 0):,} "
                f"dogleg_failed={r.get('dogleg_failed', 0):,} "
                f"straight_blockers={named_blockers}",
                flush=True,
            )
        aggregate = {}
        for s in diagnostic_stats.values():
            for key in (
                "immutable_reserved",
                "immutable_rim",
                "overlap",
                "leader_existing",
                "route",
                "leader_rim",
                "leader_graze",
            ):
                aggregate[key] = aggregate.get(key, 0) + s.get(key, 0)
        ranked = sorted(aggregate.items(), key=lambda item: (-item[1], item[0]))
        print(
            f"Planet Finder {mode}: TERMINAL REJECTION CONSTRAINTS "
            + " ".join(f"{key}={count:,}" for key, count in ranked),
            flush=True,
        )
        print(
            f"Planet Finder {mode}: TERMINAL BEST-PARTIAL deepest={deepest}/{len(order)}",
            flush=True,
        )
    def viable_candidates(item, depth):
        original_index, (symbol, name, longitude) = item
        key = (depth, name)
        stats = diagnostic_stats.setdefault(key, {
            "generated": 0,
            "viable": 0,
            "overlap": 0,
            "leader": 0,
            "route": 0,
            "immutable_reserved": 0,
            "immutable_reserved_by_obstacle": {},
            "immutable_rim": 0,
            "leader_existing": 0,
            "leader_rim": 0,
            "leader_graze": 0,
            "started": False,
            "blocked": None,
        })
        nonlocal candidates, rejected_overlap, rejected_leader, rejected_route
        w, h = label_size(mode, name)
        anchor = xy(longitude, RI - 5)
        # This generator is created for one fixed DFS prefix. The placed
        # obstacles therefore remain stable for its lifetime, so anchor-side
        # routing work can be safely reused across all candidate labels.
        route_prefix_cache = {}
        body_candidates = 0
        raw_positions = 0
        # Proposal work is local to this fixed DFS prefix. A pathological child
        # may exhaust its own stream, but must never consume the parent's
        # ability to generate the next sibling during backtracking.
        candidate_started = time.monotonic()
        candidate_last_heartbeat = candidate_started
        last_yield_at = None
        suspended_total = 0.0
        timing = {"stream_wait": 0.0, "overlap": 0.0, "existing_leader": 0.0, "route": 0.0, "final_leader": 0.0}
        legal_positions = iter(
            legal_candidate_positions(
                longitude,
                w,
                h,
                reserved,
                displacement_scale,
                diagnostic=stats,
            )
        )
        while True:
            resumed_at = time.monotonic()
            if last_yield_at is not None:
                suspended_total += max(0.0, resumed_at - last_yield_at)
                last_yield_at = None
            stream_t0 = time.monotonic()
            try:
                x, y, box = next(legal_positions)
            except StopIteration:
                break
            stream_dt = time.monotonic() - stream_t0
            timing["stream_wait"] += stream_dt
            raw_positions += 1
            body_attempts[name] += 1
            # The explosion cap belongs to the body across this entire fixed
            # ordering, not to one parent prefix. Backtracking therefore does
            # not erase evidence that this body is exploding the search tree.
            if body_attempts[name] >= budget["max_node_candidates"]:
                stats["blocked"] = "body-attempt-cap"
                print(
                    f"Planet Finder {mode}: BODY-ATTEMPT STOP order={order_index} "
                    f"depth={depth}/{len(order)} body={name} "
                    f"attempts={body_attempts[name]:,}/{budget['max_node_candidates']:,}",
                    flush=True,
                )
                raise DepthNodeBudgetExhausted(depth, name)

            # Narrow instrumentation for pathological candidate generation.
            # Report any single stage that stalls for >= 1s immediately, rather
            # than waiting for the 5s aggregate heartbeat.
            if stream_dt >= 1.0:
                print(
                    f"Planet Finder {mode}: SLOW candidate-position body={name} "
                    f"depth={depth}/{len(order)} raw={raw_positions:,} dt={stream_dt:.3f}s",
                    flush=True,
                )
            now = time.monotonic()
            if now - candidate_last_heartbeat >= 5.0:
                print(
                    f"Planet Finder {mode}: CANDIDATE HEARTBEAT order={order_index} "
                    f"depth={depth}/{len(order)} body={name} elapsed={now-candidate_started:.1f}s "
                    f"raw={raw_positions:,} viable={body_candidates:,} "
                    f"rejects[overlap={stats['overlap']:,},leader={stats['leader']:,},route={stats['route']:,}] "
                    f"time[stream-wait={timing['stream_wait']:.3f}s,overlap={timing['overlap']:.3f}s,"
                    f"existing-leader={timing['existing_leader']:.3f}s,route={timing['route']:.3f}s,"
                    f"final-leader={timing['final_leader']:.3f}s,suspended={suspended_total:.3f}s]",
                    flush=True,
                )
                candidate_last_heartbeat = now
            # Enforce the run-wide deadline inside candidate generation too.
            # Geometry/routing can otherwise keep one DFS iteration busy past the limit.
            run_elapsed = time.monotonic() - budget["started"]
            if run_elapsed >= budget["max_seconds"]:
                stats["blocked"] = "wall-clock"
                print(
                    f"Planet Finder {mode}: CANDIDATE-GENERATION STOP wall-clock budget exhausted "
                    f"order={order_index} depth={depth}/{len(order)} body={name} "
                    f"after {run_elapsed:.1f}s/{budget['max_seconds']:.1f}s "
                    f"viable={body_candidates:,}",
                    flush=True,
                )
                raise RuntimeError(
                    f"Planet Finder {mode} mode wall-clock budget exhausted "
                    f"during candidate generation for {name} after {run_elapsed:.1f}s "
                    f"(limit {budget['max_seconds']:.1f}s)"
                )
            stats["started"] = True
            # Reject geometry that is already impossible in the current DFS
            # state before admitting the proposal to the candidate pool. A
            # label overlapping an already placed label, or crossing an
            # existing leader, cannot become valid without backtracking, so it
            # must not consume candidate/search budget.
            t0 = time.monotonic()
            overlaps_placed = any(boxes_overlap(box, b, 14) for b in placed)
            timing["overlap"] += time.monotonic() - t0
            if overlaps_placed:
                rejected_overlap += 1
                stats["overlap"] += 1
                continue
            t0 = time.monotonic()
            hit_existing_leader = any(segment_hits_box(seg[i], seg[i + 1], box, 10)
                                      for seg in leaders for i in range(len(seg) - 1))
            timing["existing_leader"] += time.monotonic() - t0
            if hit_existing_leader:
                rejected_leader += 1
                stats["leader"] += 1
                stats["leader_existing"] += 1
                continue
            route_diag = route_diagnostics.setdefault((depth, name), {
                "straight_blocked": 0,
                "route_failed": 0,
                "straight_blockers": {},
                "elbows": {},
            })
            route_diag["obstacle_names"] = reserved_names + [f"placed_{i}" for i in range(len(placed))]
            t0 = time.monotonic()
            path = route(
                anchor,
                (x, y),
                reserved + placed,
                route_diag,
                # Only the 3 fixed center annotations may contain an anchor and
                # permit an initial escape. Zodiac labels are real rendered
                # obstacles; allowing escape from them can hide a leader/zodiac
                # collision in the first leader segment.
                allow_initial_escape_count=3,
                prefix_cache=route_prefix_cache,
            )
            route_dt = time.monotonic() - t0
            timing["route"] += route_dt
            if route_dt >= 1.0:
                print(
                    f"Planet Finder {mode}: SLOW route body={name} "
                    f"depth={depth}/{len(order)} raw={raw_positions:,} dt={route_dt:.3f}s "
                    f"result={'none' if path is None else 'ok'}",
                    flush=True,
                )
            if path is None:
                rejected_route += 1
                stats["route"] += 1
                continue
            # The inner zodiac rim is protected geometry, not a scoring
            # preference. Reject the route and let ordinary DFS/backtracking
            # try the next candidate; never special-case a body or week.
            if leader_hits_zodiac_rim(path):
                rejected_leader += 1
                stats["leader"] += 1
                stats["leader_rim"] += 1
                continue
            t0 = time.monotonic()
            too_close = leaders_too_close(path, leaders)
            timing["final_leader"] += time.monotonic() - t0
            if too_close:
                rejected_leader += 1
                stats["leader"] += 1
                stats["leader_graze"] += 1
                continue
            # Yield immediately: DFS tries this legal geometry before asking
            # for another route. Rejected geometry never consumes candidate budget.
            body_candidates += 1
            stats["generated"] += 1
            stats["viable"] += 1
            if body_candidates >= budget["max_node_candidates"]:
                raise DepthNodeBudgetExhausted(depth, name)
            last_yield_at = time.monotonic()
            yield box, path

    def search(depth):
        """Recursive DFS: each call owns exactly one body depth.

        Geometry rejects bad proposals before they enter this function.
        Returning from a child is the only backtracking mechanism.
        """
        nonlocal nodes, deepest, candidates, backtracks, current_body

        run_elapsed = time.monotonic() - budget["started"]
        if run_elapsed >= budget["max_seconds"]:
            raise RuntimeError(
                f"Planet Finder {mode} mode wall-clock budget exhausted "
                f"after {run_elapsed:.1f}s (limit {budget['max_seconds']:.1f}s)"
            )

        nodes += 1
        deepest = max(deepest, depth)
        depth_visits[depth] = depth_visits.get(depth, 0) + 1

        if depth == len(order):
            result = [staged[i] for i in range(len(bodies))]
            key = tuple(
                (
                    round(row[3].x, 3),
                    round(row[3].y, 3),
                    tuple((round(x, 3), round(y, 3)) for x, y in row[4]),
                )
                for row in result
            )
            if key not in solution_keys:
                solution_keys.add(key)
                valid, errors = validate_layout(mode, result)
                if valid:
                    solutions.append(result)
                    contest_keys.append(key)
                    print(
                        f"Planet Finder {mode}: complete valid candidate "
                        f"{len(solutions)}/{target_solutions} "
                        f"order={order_index} placement-order=" +
                        " > ".join(row[1] for row in result),
                        flush=True,
                    )
                else:
                    print(
                        f"Planet Finder {mode}: rejected complete layout "
                        f"order={order_index} errors=" + "; ".join(errors),
                        flush=True,
                    )
            return len(solutions) >= target_solutions

        item = order[depth]
        original_index, (symbol, name, longitude) = item
        current_body = name
        generated_here = False

        for box, path in viable_candidates(item, depth):
            generated_here = True
            candidates += 1
            placed.append(box)
            leaders.append(path)
            staged[original_index] = (symbol, name, longitude, box, path)

            child_deepest_before = deepest
            child_nodes_before = nodes
            child_backtracks_before = backtracks
            try:
                if search(depth + 1):
                    return True
            finally:
                staged.pop(original_index, None)
                leaders.pop()
                placed.pop()

            backtracks += 1
            # Prefix diagnostic: when an individually legal candidate cannot
            # extend to a complete layout, report how far its child subtree
            # actually reached. This observes DFS behavior without changing it.
            if mode == FinderMode.MIXED and depth <= 1:
                print(
                    f"Planet Finder {mode}: PREFIX BACKTRACK "
                    f"depth={depth}/{len(order)} body={name} "
                    f"candidate={candidates} "
                    f"child-deepest={deepest}/{len(order)} "
                    f"new-depth={deepest > child_deepest_before} "
                    f"child-nodes={nodes - child_nodes_before} "
                    f"child-backtracks={backtracks - child_backtracks_before}",
                    flush=True,
                )

        if not generated_here:
            dead_key = (depth, name)
            dead_end_visits[dead_key] = dead_end_visits.get(dead_key, 0) + 1
            # Reuse the same per-body cap: too many candidates in one prefix
            # or too many zero-candidate prefixes both identify a squeaky wheel.
            if dead_end_visits[dead_key] >= budget["max_node_candidates"]:
                print(
                    f"Planet Finder {mode}: REPEATED-DEAD-END STOP order={order_index} "
                    f"depth={depth}/{len(order)} body={name} "
                    f"dead-ends={dead_end_visits[dead_key]:,}/{budget['max_node_candidates']:,}",
                    flush=True,
                )
                raise DepthNodeBudgetExhausted(depth, name)
            stats = diagnostic_stats[(depth, name)]
            print(
                f"Planet Finder {mode}: dead end order={order_index} "
                f"depth={depth}/{len(order)} body={name} "
                f"status={'evaluated' if stats.get('started') else 'not-evaluated'} "
                f"generated={stats['generated']:,} viable={stats['viable']:,} "
                f"rejects[overlap={stats['overlap']:,},leader={stats['leader']:,},"
                f"route={stats['route']:,}]",
                flush=True,
            )
        return False

    try:
        exhausted = not search(0)
    except DepthNodeBudgetExhausted as exc:
        # Hitting the per-body/depth cap is the squeaky-wheel signal.  Report
        # this fixed ordering, then let layout() discard the whole DFS napkin
        # and retry from a clean state with that body promoted to first.
        dump_diagnostics(
            f"node budget exhausted at depth={exc.depth}/{len(order)} body={exc.name}"
        )
        raise
    except RuntimeError as exc:
        dump_diagnostics(f"runtime failure: {exc}")
        raise

    if exhausted:
        dump_diagnostics("search exhausted without a complete solution")

    elapsed = time.monotonic() - started
    print(
        f"Planet Finder {mode}: fixed-order summary order={order_index} "
        f"exhausted={exhausted} elapsed={elapsed:.2f}s nodes={nodes:,} "
        f"deepest={deepest}/{len(order)} candidates={candidates:,} "
        f"rejects[overlap={rejected_overlap:,},leader={rejected_leader:,},"
        f"route={rejected_route:,}] backtracks={backtracks:,} "
        f"solutions={len(solutions)}",
        flush=True,
    )
    blocker = None
    if exhausted:
        # deepest is a reached DFS depth; the body at that depth is the first
        # body that could not be placed. If the tree reached completion, use
        # the final body as the ordering feedback.
        blocker_depth = min(deepest, len(order) - 1)
        blocker = order[blocker_depth][1][1]
    blocker_stats = None
    if blocker is not None:
        blocker_depth = next(
            (depth for depth, item in enumerate(order) if item[1][1] == blocker),
            None,
        )
        if blocker_depth is not None:
            s = diagnostic_stats.get((blocker_depth, blocker), {})
            blocker_stats = {
                "immutable_reserved": s.get("immutable_reserved", 0),
                "immutable_rim": s.get("immutable_rim", 0),
                "placed_overlap": s.get("overlap", 0),
                "existing_leader": s.get("leader_existing", 0),
                "route": s.get("route", 0),
                "leader_rim": s.get("leader_rim", 0),
                "leader_graze": s.get("leader_graze", 0),
            }
    return SearchOutcome(
        "SOLVED" if len(solutions) >= target_solutions else "EXHAUSTED",
        solutions,
        contest_keys,
        blocker,
        blocker_stats,
    )


def new_search_budget():
    """Create the per-body candidate and wall-clock safety limits."""
    max_node_candidates = int(os.environ.get("PLANET_FINDER_MAX_NODE_CANDIDATES", "200"))
    if max_node_candidates <= 0:
        raise ValueError("PLANET_FINDER_MAX_NODE_CANDIDATES must be positive")
    max_seconds = max(1.0, float(os.environ.get("PLANET_FINDER_MAX_SECONDS", "180")))
    # This object contains limits only.  It deliberately contains no clock
    # state: every notation mode starts its own clock inside layout().
    return {
        "max_node_candidates": max_node_candidates,
        "max_seconds": max_seconds,
    }

def layout(
    mode: FinderMode,
    bodies: list[tuple[str, str, float]],
    target_solutions: int | None = None,
    budget: dict | None = None,
    context_label: str | None = None,
):
    """Find collision-free layouts with deterministic canonical-order DFS.

    Candidate generation is lazy. Geometry rejects impossible proposals before
    they enter DFS. Search limits are safety ceilings, not placement policy.
    """
    mode = FinderMode(mode)
    canonical_index = {name: i for i, name in enumerate(CANONICAL)}
    indexed = list(enumerate(bodies))
    indexed.sort(key=lambda item: canonical_index[item[1][1]])

    if len(indexed) != len(CANONICAL):
        raise RuntimeError(
            f"Planet Finder body set has {len(indexed)} bodies; expected {len(CANONICAL)}"
        )
    if {name for _, (_, name, _) in indexed} != set(CANONICAL):
        raise RuntimeError("Planet Finder body set does not match the canonical Solar-System objects")

    if target_solutions is None:
        target_solutions = max(1, int(os.environ.get("PLANET_FINDER_CANDIDATES", "5")))

    if budget is None:
        budget = new_search_budget()

    # One clock per mode, always.  Copy the limits so callers may safely reuse
    # one configuration object without ever sharing elapsed time between Greek,
    # Latin, and Mixed.
    budget = dict(budget)
    budget["started"] = time.monotonic()
    print(
        f"Planet Finder {mode}: MODE CLOCK STARTED: "
        f"limit={budget['max_seconds']:.1f}s",
        flush=True,
    )

    order = indexed
    all_solutions = []
    contest_keys = []
    order_index = 0
    refinement_scales = (2.0, 1.5, 1.0, 0.5, 0.25)
    refinement_index = 0
    attempted_orders = set()
    # Preserve controller history across refinements for terminal diagnosis.
    refinement_history = []

    # Explicit search-controller state machine. Search attempts report events;
    # only the controller changes ordering or placement refinement.
    #
    # SEARCH_ORDER -> SCORE    on SOLVED
    # SEARCH_ORDER -> CAPPED   on CAPPED(body)
    # SEARCH_ORDER -> PROMOTE  on EXHAUSTED(blocker)
    # CAPPED       -> SEARCH_ORDER after promoting the capped body
    #                 (a cap is incomplete evidence and may never refine)
    # PROMOTE      -> SEARCH_ORDER when the exhausted blocker ordering is new
    # PROMOTE      -> REFINE   when EXHAUSTED promotion closes an ordering cycle
    # REFINE       -> SEARCH_ORDER at the next placement scale
    state = "SEARCH_ORDER"
    promote_body = None

    while state != "SCORE":
        if time.monotonic() - budget["started"] >= budget["max_seconds"]:
            raise RuntimeError(
                f"Planet Finder {mode} mode wall-clock budget exhausted "
                f"(limit {budget['max_seconds']:.1f}s)"
            )

        if state == "REFINE":
            if refinement_index + 1 >= len(refinement_scales):
                final_sequence = " > ".join(item[1][1] for item in order)
                print(
                    f"Planet Finder {mode}: TERMINAL SEARCH DIAGNOSTIC "
                    f"refinements={len(refinement_scales)} attempts={len(refinement_history)} "
                    f"final-sequence={final_sequence}",
                    flush=True,
                )
                for i, event in enumerate(refinement_history, 1):
                    print(
                        f"Planet Finder {mode}: TERMINAL HISTORY attempt={i} "
                        f"refinement={event['scale']:g} outcome={event['kind']} "
                        f"blocker={event['blocker']} contestants={event['contestants']}/{target_solutions} "
                        f"rejects={event.get('rejection_stats') or 'see fixed-order terminal diagnostic'} "
                        f"sequence={' > '.join(event['order'])}",
                        flush=True,
                    )
                raise RuntimeError(
                    f"Planet Finder {mode}: exhausted all placement refinements "
                    f"through {refinement_scales[refinement_index]:g} label-lengths; "
                    f"see TERMINAL SEARCH DIAGNOSTIC above"
                )
            refinement_index += 1
            # Refinement changes placement geometry, not ordering knowledge.
            # Carry the squeaky-wheel ordering learned at the coarser scale
            # into the finer search; only the per-refinement visit history is
            # reset so that this ordering can be tried under the new geometry.
            attempted_orders.clear()
            promote_body = None
            print(
                f"Planet Finder {mode}: REFINEMENT ADVANCE "
                f"to {refinement_scales[refinement_index]:g} label-lengths; "
                "preserving learned sequence="
                + " > ".join(item[1][1] for item in order),
                flush=True,
            )
            state = "SEARCH_ORDER"
            continue

        if state == "CAPPED":
            # A node cap means only that this ordering was not searched to
            # completion. It is not evidence that the geometry is exhausted,
            # so it must never advance placement refinement.
            promote_index = next(
                (i for i, item in enumerate(order) if item[1][1] == promote_body),
                None,
            )
            if promote_index is None:
                raise RuntimeError(
                    f"Planet Finder {mode}: capped body {promote_body} is absent from ordering"
                )
            promoted_order = [
                order[promote_index],
                *order[:promote_index],
                *order[promote_index + 1:],
            ]
            promoted_names = tuple(item[1][1] for item in promoted_order)
            promoted_key = (refinement_index, promoted_names)
            if promoted_key in attempted_orders:
                # Move-to-front promotion has closed a CAPPED cycle.  The cap
                # is incomplete evidence, so refinement remains forbidden, but
                # repeating the same promotion is equally uninformative.  Keep
                # the capped body first and deterministically rotate the tail
                # until we find an ordering not yet searched at this scale.
                #
                # This preserves the squeaky-wheel lesson while exploring a
                # genuinely different interaction among the remaining bodies.
                head = promoted_order[0]
                tail = promoted_order[1:]
                alternate_order = None
                for shift in range(1, len(tail)):
                    candidate = [head, *tail[shift:], *tail[:shift]]
                    candidate_names = tuple(item[1][1] for item in candidate)
                    candidate_key = (refinement_index, candidate_names)
                    if candidate_key not in attempted_orders:
                        alternate_order = candidate
                        break
                if alternate_order is None:
                    raise RuntimeError(
                        f"Planet Finder {mode}: node-cap ordering space closed at "
                        f"{refinement_scales[refinement_index]:g} label-lengths; "
                        "search remains inconclusive, so refinement is forbidden"
                    )
                order = alternate_order
                alternate_names = tuple(item[1][1] for item in order)
                print(
                    f"Planet Finder {mode}: CAPPED CYCLE CLOSED body={promote_body}; "
                    "trying deterministic tail rotation without refinement sequence="
                    + " > ".join(alternate_names),
                    flush=True,
                )
                state = "SEARCH_ORDER"
                continue
            order = promoted_order
            print(
                f"Planet Finder {mode}: CAPPED PROMOTE body={promote_body}; "
                "incomplete search, preserving refinement and restarting sequence="
                + " > ".join(promoted_names),
                flush=True,
            )
            state = "SEARCH_ORDER"
            continue

        if state == "PROMOTE":
            promote_index = next(
                (i for i, item in enumerate(order) if item[1][1] == promote_body),
                None,
            )
            if promote_index is None:
                raise RuntimeError(
                    f"Planet Finder {mode}: promotion body {promote_body} is absent from ordering"
                )
            promoted_order = [
                order[promote_index],
                *order[:promote_index],
                *order[promote_index + 1:],
            ]
            promoted_names = tuple(item[1][1] for item in promoted_order)
            promoted_key = (refinement_index, promoted_names)
            if promoted_key in attempted_orders:
                print(
                    f"Planet Finder {mode}: PROMOTION CYCLE CLOSED body={promote_body} "
                    f"at {refinement_scales[refinement_index]:g} label-lengths; refining",
                    flush=True,
                )
                state = "REFINE"
            else:
                order = promoted_order
                print(
                    f"Planet Finder {mode}: PROMOTE body={promote_body}; "
                    "discarding fixed-order search state and restarting with sequence="
                    + " > ".join(promoted_names),
                    flush=True,
                )
                state = "SEARCH_ORDER"
            continue

        if state != "SEARCH_ORDER":
            raise RuntimeError(f"Planet Finder {mode}: invalid controller state {state}")

        order_names = tuple(item[1][1] for item in order)
        order_key = (refinement_index, order_names)
        if order_key in attempted_orders:
            state = "REFINE"
            continue
        attempted_orders.add(order_key)
        order_index += 1
        print(
            f"Planet Finder {mode}: squeaky-wheel lazy DFS "
            f"{context_label + ' ' if context_label else ''}"
            f"order={order_index} target={target_solutions} "
            f"max-node-candidates={budget['max_node_candidates']:,} "
            f"refinement={refinement_scales[refinement_index]:g} label-lengths "
            f"sequence=" + " > ".join(order_names),
            flush=True,
        )

        try:
            outcome = _solve_order(
                mode,
                bodies,
                order,
                budget,
                target_solutions=target_solutions,
                order_index=order_index,
                total_orders=None,
                context_label=context_label,
                displacement_scale=refinement_scales[refinement_index],
            )
        except DepthNodeBudgetExhausted as exc:
            # The fixed-order solver already emitted its detailed terminal
            # diagnostic. CAPPED currently has no structured stats payload;
            # keep that distinction explicit rather than inventing counts.
            outcome = SearchOutcome("CAPPED", [], [], exc.name, None)

        if outcome.kind == "SOLVED":
            all_solutions = outcome.solutions
            contest_keys = outcome.contest_keys
            state = "SCORE"
            continue

        if outcome.kind not in ("CAPPED", "EXHAUSTED") or not outcome.blocker:
            raise RuntimeError(
                f"Planet Finder {mode}: invalid search outcome "
                f"kind={outcome.kind} blocker={outcome.blocker}"
            )

        all_solutions = outcome.solutions
        contest_keys = outcome.contest_keys
        promote_body = outcome.blocker
        refinement_history.append({
            "scale": refinement_scales[refinement_index],
            "kind": outcome.kind,
            "blocker": promote_body,
            "contestants": len(all_solutions),
            "order": order_names,
            "rejection_stats": outcome.rejection_stats,
        })
        print(
            f"Planet Finder {mode}: SEARCH OUTCOME {outcome.kind} "
            f"body={promote_body} contestants={len(all_solutions)}/{target_solutions}",
            flush=True,
        )
        # EXHAUSTED is proof about the complete fixed-order search and may
        # participate in the refinement state machine. CAPPED is only a safety
        # interruption and gets its own non-refining transition.
        state = "CAPPED" if outcome.kind == "CAPPED" else "PROMOTE"

    if not all_solutions:
        raise RuntimeError(
            f"No collision-free Planet Finder layout found in {mode} mode"
        )

    def score(result):
        total_length = 0.0
        elbows = 0
        radial_error = 0.0
        tangential_error = 0.0
        for _, _, longitude, box, path in result:
            total_length += sum(
                math.hypot(b[0]-a[0], b[1]-a[1])
                for a, b in zip(path, path[1:])
            )
            elbows += max(0, len(path) - 2)
            natural = xy(longitude, 345)
            radial_error += abs(math.hypot(box.x-CX, box.y-CY) - 345)
            tangential_error += math.hypot(box.x-natural[0], box.y-natural[1])
        return (elbows, total_length, tangential_error, radial_error)

    scored = sorted((score(result), i, result) for i, result in enumerate(all_solutions))
    best_score, best_index, best = scored[0]

    # Contest-validity diagnostic: a configured N-contestant competition must
    # actually contain N distinct, independently validated complete layouts.
    # Viability is established before a result enters all_solutions; the
    # uniqueness key prevents duplicate layouts from becoming contestants.
    contest_count = len(all_solutions)
    unique_count = len(set(contest_keys))
    contest_valid = (
        contest_count == target_solutions
        and unique_count == contest_count
        and contest_count == len(scored)
    )
    print(
        f"Planet Finder {mode}: CONTEST AUDIT "
        f"requested={target_solutions} contestants={contest_count} "
        f"unique={unique_count} scored={len(scored)} "
        f"status={'VALID' if contest_valid else 'INVALID'}",
        flush=True,
    )
    for rank, (candidate_score, candidate_index, _) in enumerate(scored, 1):
        print(
            f"Planet Finder {mode}: CONTESTANT rank={rank} "
            f"candidate={candidate_index + 1} "
            f"score[elbows={candidate_score[0]},length={candidate_score[1]:.1f},"
            f"displacement={candidate_score[2]:.1f},radial={candidate_score[3]:.1f}]",
            flush=True,
        )
    if not contest_valid:
        raise RuntimeError(
            f"Planet Finder {mode}: contest validity failure "
            f"requested={target_solutions} contestants={contest_count} "
            f"unique={unique_count} scored={len(scored)}"
        )

    print(
        f"Planet Finder {mode}: selected candidate {best_index + 1}/{len(all_solutions)} "
        f"{context_label + ' ' if context_label else ''}"
        f"score[elbows={best_score[0]},length={best_score[1]:.1f},"
        f"displacement={best_score[2]:.1f},radial={best_score[3]:.1f}]",
        flush=True,
    )
    return best

def validate_layout(mode: str, result) -> tuple[bool, list[str]]:
    """Recheck a completed layout independently before rendering it."""
    errors = []
    reserved = reserved_boxes(mode)
    boxes = [row[3] for row in result]
    paths = [row[4] for row in result]

    # Labels must not overlap reserved annotations/zodiac labels or each other.
    for i, box in enumerate(boxes):
        name = result[i][1]
        for j, obstacle in enumerate(reserved):
            if boxes_overlap(box, obstacle, 14):
                errors.append(f"{name}: label overlaps reserved obstacle {j}")
        for j in range(i):
            if boxes_overlap(box, boxes[j], 14):
                errors.append(f"{name}: label overlaps {result[j][1]}")

    # Every leader must remain clear of every label except its own endpoint.
    for i, path in enumerate(paths):
        name = result[i][1]
        for j, box in enumerate(boxes):
            if i == j:
                continue
            for a, b in zip(path, path[1:]):
                if segment_hits_box(a, b, box, 10):
                    errors.append(f"{name}: leader crosses {result[j][1]} label")
                    break
        for j, obstacle in enumerate(reserved):
            # The route solver permits an initial escape from an obstacle
            # containing the body's anchor. Do not reinterpret that legal
            # escape as a post-layout collision; later segments must be clear.
            for seg_index, (a, b) in enumerate(zip(path, path[1:])):
                if seg_index == 0 and (
                    obstacle.left - 8 <= a[0] <= obstacle.right + 8 and
                    obstacle.top - 8 <= a[1] <= obstacle.bottom + 8
                ):
                    continue
                if segment_hits_box(a, b, obstacle, 8):
                    errors.append(f"{name}: leader crosses reserved obstacle {j}")
                    break

    # The inner zodiac rim is protected geometry. Recheck this independently
    # after search so no stale/future routing bug can render a leader touching
    # or crossing the circle.
    for i, path in enumerate(paths):
        if leader_hits_zodiac_rim(path):
            errors.append(f"{result[i][1]}: leader collides with inner zodiac border")

    # Leaders are mutually exclusive geometry.  This is intentionally a
    # second, independent check after proposal-time rejection so a stale or
    # future search-state bug can never render crossing/grazing leaders.
    for i, path in enumerate(paths):
        for j in range(i):
            if leaders_too_close(path, [paths[j]]):
                errors.append(
                    f"{result[i][1]}: leader crosses or grazes {result[j][1]} leader"
                )

    # Recheck the hard inner-rim rule independently of candidate generation.
    rim_limit = RI - 14
    for i, box in enumerate(boxes):
        if any(
            math.hypot(px - CX, py - CY) >= rim_limit
            for px in (box.left, box.right)
            for py in (box.top, box.bottom)
        ):
            errors.append(f"{result[i][1]}: label collides with inner zodiac border")

    return not errors, errors


def polyline(points):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{pts}" fill="none" stroke="#777" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'


def render(
    year: int,
    week: int,
    monday: date,
    mode: FinderMode,
    bodies: list[tuple[str, str, float]],
    budget: dict | None = None,
    context_label: str | None = None,
) -> str:
    mode = FinderMode(mode)
    labels = {
        FinderMode.GREEK: "Greek / Symbols",
        FinderMode.LATIN: "Latin",
        FinderMode.MIXED: "Mixed / Learner",
    }
    title = labels[mode]
    placed = layout(mode, bodies, budget=budget, context_label=context_label)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="1400" viewBox="0 0 {W} {H}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Georgia,"Times New Roman",serif;fill:#111!important;color:#111!important;-webkit-text-fill-color:#111!important}.sans{font-family:Arial,Helvetica,sans-serif}</style>',
        f'<text x="{CX}" y="72" text-anchor="middle" font-size="38" font-weight="700">ISO {year}-W{week:02d} Planet Finder</text>',
        f'<text x="{CX}" y="110" text-anchor="middle" font-size="23">{title} · Monday, {monday.strftime("%B")} {monday.day}, {year} · 00:00 UTC</text>',
        f'<circle cx="{CX}" cy="{CY}" r="{RO}" fill="none" stroke="#111" stroke-width="4"/>',
        f'<circle cx="{CX}" cy="{CY}" r="{RI}" fill="none" stroke="#111" stroke-width="2"/>',
    ]
    for i in range(12):
        x1, y1 = xy(i * 30, RI)
        x2, y2 = xy(i * 30, RO)
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#111" stroke-width="2"/>')
    for i, (symbol, name) in enumerate(SIGNS):
        x, y = xy(i * 30 + 15, (RI + RO) / 2)
        if mode == "greek":
            text, fs = symbol + "\ufe0e", 48
        elif mode == "latin":
            text, fs = name, 24
        else:
            text, fs = f'{symbol}\ufe0e {name}', 22
        out.append(f'<text x="{x:.1f}" y="{y+10:.1f}" text-anchor="middle" font-size="{fs}">{html.escape(text)}</text>')
    # Fixed geometric annotation: 0° Aries is the 9-o'clock boundary.
    # Keep it deterministic and independent of body-label placement.
    aries_x, aries_y = xy(0, RI)
    out.append(
        f'<text x="{aries_x - 12:.1f}" y="{aries_y + 7:.1f}" '
        'text-anchor="end" font-size="20" class="sans">0° Aries</text>'
    )

    for symbol, name, _, box, path in placed:
        out.append(polyline(path))
        if mode == "greek":
            out.append(f'<circle cx="{box.x:.1f}" cy="{box.y:.1f}" r="29" fill="white" stroke="#111"/>')
            out.append(f'<text x="{box.x:.1f}" y="{box.y+13:.1f}" text-anchor="middle" font-size="44">{html.escape(symbol)}\ufe0e</text>')
        else:
            text = name if mode == "latin" else f"{symbol}\ufe0e {name}"
            out.append(f'<rect x="{box.left:.1f}" y="{box.top:.1f}" width="{box.w:.1f}" height="{box.h:.1f}" rx="10" fill="white" stroke="#111"/>')
            out.append(f'<text x="{box.x:.1f}" y="{box.y+7:.1f}" text-anchor="middle" font-size="18">{html.escape(text)}</text>')

    out.extend([
        f'<text x="{CX}" y="682" text-anchor="middle" font-size="28" font-weight="700">Tropical ecliptic longitude</text>',
        f'<text x="{CX}" y="722" text-anchor="middle" font-size="22">0° Aries at 9:00 · zodiac increases counterclockwise</text>',
        f'<text x="{CX}" y="757" text-anchor="middle" font-size="22">12 equal sectors · 30° each</text>',
        '</svg>',
    ])
    return "\n".join(out) + "\n"


def generate_week(year: int, week: int):
    if not 1 <= week <= week_count(year):
        raise ValueError(f"Invalid ISO week {year}-W{week:02d}")
    monday = date.fromisocalendar(year, week, 1)
    needed = {BODY_NAMES[name] for name in CANONICAL}
    engine = StarAlmanackEphemeris()
    generated = computed_ephemeris(year, engine)
    values = {key: generated[key][week - 1][0] for key in needed}
    bodies = [(BODY_SYMBOLS[BODY_NAMES[name]], name, values[BODY_NAMES[name]] % 360) for name in CANONICAL]
    outdir = ROOT / "almanack" / str(year) / f"W{week:02d}" / "finders"
    outdir.mkdir(parents=True, exist_ok=True)
    filenames = {
        FinderMode.GREEK: "planet-finder-greek-symbols.svg",
        FinderMode.LATIN: "planet-finder-latin.svg",
        FinderMode.MIXED: "planet-finder-mixed-learner.svg",
    }
    for mode, filename in filenames.items():
        (outdir / filename).write_text(render(year, week, monday, mode, bodies), encoding="utf-8")
    print(f"Generated collision-free Planet Finders for ISO {year}-W{week:02d} from internal calculations")


def parse_args():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--current", action="store_true", help="generate the current UTC ISO week")
    g.add_argument("--year", type=int, help="ISO week-year")
    p.add_argument("--week", type=int, help="ISO week number; required with --year")
    args = p.parse_args()
    if args.year is not None and args.week is None:
        p.error("--week is required with --year")
    return args


def main():
    args = parse_args()
    if args.current:
        today = date.today()
        iso = today.isocalendar()
        year, week = iso.year, iso.week
    else:
        year, week = args.year, args.week
    generate_week(year, week)


if __name__ == "__main__":
    main()