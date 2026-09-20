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
            # Rendered at 24 px Georgia.  Use a conservative text envelope
            # rather than the former narrow character-count estimate.
            boxes.append(Box(x, y, max(108, 16 * len(name)), 58))
        else:
            # Mixed mode renders "<glyph> <name>" at 22 px.  The zodiac glyph
            # is substantially wider than an ordinary Latin character.
            boxes.append(Box(x, y, max(148, 16 * len(name) + 58), 58))
    return boxes


def candidate_positions(longitude: float):
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
    displacement_scales = (2.0, 1.5, 1.0, 0.5, 0.25)
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
    for scale in displacement_scales:
        shift = label_length * scale
        yield from offer(preferred_radii, (-shift, shift))

    expanded_radii = tuple(range(400, 79, -20))
    yield from offer(expanded_radii, (0.0,))
    for scale in displacement_scales:
        shift = label_length * scale
        yield from offer(expanded_radii, (-shift, shift))


def legal_candidate_positions(longitude: float, w: float, h: float, reserved: list[Box]):
    """Yield only proposals that are legal against immutable chart geometry.
    Reserved center annotations and zodiac labels never move, so a candidate
    that overlaps one can never become valid through DFS backtracking. Reject
    it here, before it enters the search candidate pool or consumes budget.
    """
    for x, y in candidate_positions(longitude):
        box = Box(x, y, w, h)
        if any(boxes_overlap(box, obstacle, 14) for obstacle in reserved):
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



class CandidateBudgetExhausted(RuntimeError):
    """Signal that the run-wide viable-candidate budget is exhausted."""


class DepthNodeBudgetExhausted(RuntimeError):
    """Signal that a body-depth node budget is exhausted for this DFS tree."""

    def __init__(self, depth: int, name: str):
        super().__init__(f"node budget exhausted at depth {depth} for {name}")
        self.depth = depth
        self.name = name


def _solve_order(mode: str, bodies, order, budget, target_solutions=5, order_index=1, total_orders=None, context_label=None):
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
    diagnostic_stats = {}
    route_diagnostics = {}
    solutions = []
    solution_keys = set()
    current_body = "-"
    exhausted = False
    def dump_diagnostics(reason):
        order_names = " > ".join(item[1][1] for item in order)
        print(
            f"Planet Finder {mode}: TERMINAL {context_label + ' ' if context_label else ''}reason={reason} order={order_index}"
            f"{('/' + str(total_orders)) if total_orders else ''} "
            f"nodes={nodes:,} deepest={deepest}/{len(order)} current_body={current_body} "
            f"candidates={candidates:,} global_candidates={budget['candidates']:,}/"
            f"{budget['max_candidates']:,} rejects[overlap={rejected_overlap:,},"
            f"leader={rejected_leader:,},route={rejected_route:,}] "
            f"backtracks={backtracks:,}",
            flush=True,
        )
        print(f"Planet Finder {mode}: TERMINAL ORDER sequence={order_names}", flush=True)
        for (depth, name), s in sorted(diagnostic_stats.items()):
            print(
                f"Planet Finder {mode}: TERMINAL BODY depth={depth}/{len(order)} body={name} "
                f"status={'evaluated' if s.get('started') else ('blocked-' + s['blocked'] if s.get('blocked') else 'not-evaluated')} "
                f"generated={s['generated']:,} viable={s['viable']:,} "
                f"rejects[overlap={s['overlap']:,},leader={s['leader']:,},route={s['route']:,}]",
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
        print(
            f"Planet Finder {mode}: TERMINAL BEST-PARTIAL deepest={deepest}/{len(order)}",
            flush=True,
        )
    def viable_candidates(item, depth):
        original_index, (symbol, name, longitude) = item
        key = (depth, name)
        stats = diagnostic_stats.setdefault(key, {
            "generated": 0, "viable": 0, "overlap": 0, "leader": 0, "route": 0, "started": False, "blocked": None,
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
        legal_positions = iter(legal_candidate_positions(longitude, w, h, reserved))
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
            # Candidate production is lazy. Geometry owns geometry; the search
            # controller owns limits. The only run-wide limits checked here are
            # the same hard safety limits used by DFS.
            if budget["candidates"] >= budget["max_candidates"]:
                stats["blocked"] = "global-budget"
                raise CandidateBudgetExhausted("Planet Finder candidate budget exhausted")
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
                    f"Planet Finder run-wide wall-clock budget exhausted in {mode} mode "
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
                allow_initial_escape_count=len(reserved),
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
            t0 = time.monotonic()
            too_close = leaders_too_close(path, leaders)
            timing["final_leader"] += time.monotonic() - t0
            if too_close:
                rejected_leader += 1
                stats["leader"] += 1
                continue
            # Yield immediately: DFS tries this legal geometry before asking
            # for another route. Rejected geometry never consumes candidate budget.
            body_candidates += 1
            stats["generated"] += 1
            stats["viable"] += 1
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
                f"Planet Finder run-wide wall-clock budget exhausted in {mode} mode "
                f"after {run_elapsed:.1f}s (limit {budget['max_seconds']:.1f}s)"
            )

        # Bound the search-tree explosion at each body depth. This counter is
        # shared across every recursive re-entry at the same depth, so a body
        # such as Neptune cannot receive a fresh allowance for every Uranus
        # parent. Once the depth has created the configured number of nodes,
        # close that level and let ordinary recursion backtrack upward.
        if depth < len(order) and depth_visits.get(depth, 0) >= budget["max_node_candidates"]:
            name = order[depth][1][1]
            print(
                f"Planet Finder {mode}: NODE-BUDGET STOP order={order_index} "
                f"depth={depth}/{len(order)} body={name} "
                f"visits={depth_visits.get(depth, 0):,}/{budget['max_node_candidates']:,}",
                flush=True,
            )
            # This cap is shared across the whole depth, not one parent prefix.
            # Once it is exhausted, no remaining ancestor sibling can produce a
            # complete layout without crossing this closed level. Propagate the
            # stop through the recursive stack instead of manufacturing doomed
            # siblings at shallower depths.
            raise DepthNodeBudgetExhausted(depth, name)

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
            if budget["candidates"] >= budget["max_candidates"]:
                raise CandidateBudgetExhausted("Planet Finder candidate budget exhausted")

            candidates += 1
            budget["candidates"] += 1
            placed.append(box)
            leaders.append(path)
            staged[original_index] = (symbol, name, longitude, box, path)

            try:
                if search(depth + 1):
                    return True
            finally:
                staged.pop(original_index, None)
                leaders.pop()
                placed.pop()

            backtracks += 1

        if not generated_here:
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
    except CandidateBudgetExhausted:
        dump_diagnostics("run-wide candidate budget exhausted")
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
        f"global_candidates={budget['candidates']:,}/{budget['max_candidates']:,} "
        f"rejects[overlap={rejected_overlap:,},leader={rejected_leader:,},"
        f"route={rejected_route:,}] backtracks={backtracks:,} "
        f"solutions={len(solutions)}",
        flush=True,
    )
    return solutions


def new_search_budget(max_candidates: int | None = None):
    """Create the shared run-wide candidate and wall-clock safety limits."""
    if max_candidates is None:
        max_candidates = int(os.environ.get("PLANET_FINDER_MAX_CANDIDATES", "1000000"))
    if max_candidates <= 0:
        raise ValueError("PLANET_FINDER_MAX_CANDIDATES must be positive")
    max_node_candidates = int(os.environ.get("PLANET_FINDER_MAX_NODE_CANDIDATES", "200"))
    if max_node_candidates <= 0:
        raise ValueError("PLANET_FINDER_MAX_NODE_CANDIDATES must be positive")
    max_seconds = max(1.0, float(os.environ.get("PLANET_FINDER_MAX_SECONDS", "90")))
    # Start the wall-clock budget lazily at the first actual layout search.
    # Ephemeris setup/kernel work must not consume the Planet Finder search ceiling.
    return {
        "candidates": 0,
        "max_candidates": max_candidates,
        "max_node_candidates": max_node_candidates,
        "max_seconds": max_seconds,
        "started": None,
    }

def layout(
    mode: str,
    bodies: list[tuple[str, str, float]],
    target_solutions: int | None = None,
    budget: dict | None = None,
    context_label: str | None = None,
):
    """Find collision-free layouts with deterministic canonical-order DFS.

    Candidate generation is lazy. Geometry rejects impossible proposals before
    they enter DFS. Search limits are safety ceilings, not placement policy.
    """
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
    if budget.get("started") is None:
        budget["started"] = time.monotonic()
        print(
            f"Planet Finder SEARCH CLOCK STARTED: limit={budget['max_seconds']:.1f}s",
            flush=True,
        )

    order = indexed
    attempted_orders = set()
    all_solutions = []
    order_index = 0

    # Squeaky-wheel ordering: a body that hits the per-depth node cap is not
    # merely stopped.  That cap identifies the body currently exploding the
    # tree.  Throw away this fixed-order DFS state, promote that body to the
    # front, and begin a completely fresh recursive search.
    while True:
        order_key = tuple(item[1][1] for item in order)
        if order_key in attempted_orders:
            break
        attempted_orders.add(order_key)
        order_index += 1

        print(
            f"Planet Finder {mode}: squeaky-wheel lazy DFS "
            f"{context_label + ' ' if context_label else ''}"
            f"order={order_index} target={target_solutions} "
            f"max-node-candidates={budget['max_node_candidates']:,} "
            f"max-candidates={budget['max_candidates']:,} "
            f"sequence=" + " > ".join(item[1][1] for item in order),
            flush=True,
        )

        try:
            all_solutions = _solve_order(
                mode,
                bodies,
                order,
                budget,
                target_solutions=target_solutions,
                order_index=order_index,
                total_orders=None,
                context_label=context_label,
            )
        except DepthNodeBudgetExhausted as exc:
            squeaky_index = next(
                (i for i, item in enumerate(order) if item[1][1] == exc.name),
                None,
            )
            if squeaky_index is None:
                raise
            if squeaky_index == 0:
                print(
                    f"Planet Finder {mode}: squeaky wheel {exc.name} already first; "
                    "cannot promote further",
                    flush=True,
                )
                all_solutions = []
                break

            order = [order[squeaky_index], *order[:squeaky_index], *order[squeaky_index + 1:]]
            print(
                f"Planet Finder {mode}: SQUEAKY-WHEEL PROMOTE body={exc.name} "
                f"after hitting {budget['max_node_candidates']:,}; "
                "discarding fixed-order search state and restarting with sequence="
                + " > ".join(item[1][1] for item in order),
                flush=True,
            )
            continue
        except CandidateBudgetExhausted:
            all_solutions = []

        break

    if not all_solutions:
        raise RuntimeError(
            f"No collision-free Planet Finder layout found in {mode} mode after "
            f"{budget['candidates']:,} candidate evaluations"
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
    mode: str,
    bodies: list[tuple[str, str, float]],
    budget: dict | None = None,
    context_label: str | None = None,
) -> str:
    labels = {"greek": "Greek / Symbols", "latin": "Latin", "mixed": "Mixed / Learner"}
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
        "greek": "planet-finder-greek-symbols.svg",
        "latin": "planet-finder-latin.svg",
        "mixed": "planet-finder-mixed-learner.svg",
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