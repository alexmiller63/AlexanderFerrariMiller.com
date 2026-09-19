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


def label_size(mode: str, name: str) -> tuple[float, float]:
    if mode == "greek":
        return 64, 64
    if mode == "latin":
        return max(104, 13 * len(name) + 28), 50
    return max(132, 13 * len(name) + 68), 50


def reserved_boxes(mode: str) -> list[Box]:
    boxes = [Box(CX, 682, 520, 40), Box(CX, 722, 690, 34), Box(CX, 757, 440, 34)]
    for i, (_, name) in enumerate(SIGNS):
        x, y = xy(i * 30 + 15, (RI + RO) / 2)
        if mode == "greek":
            boxes.append(Box(x, y, 66, 66))
        elif mode == "latin":
            boxes.append(Box(x, y, max(92, 14 * len(name)), 46))
        else:
            boxes.append(Box(x, y, max(122, 14 * len(name) + 45), 46))
    return boxes


def candidate_positions(longitude: float):
    """Yield deterministic label positions, preferred positions first."""
    preferred_radii = (345, 300, 255, 210, 390, 165, 120)
    preferred_shifts = (0, -42, 42, -84, 84, -126, 126, -168, 168, -210, 210)
    theta = math.radians(180 + longitude)
    tx, ty = -math.sin(theta), -math.cos(theta)
    seen: set[tuple[int, int]] = set()

    def offer(radii, shifts):
        for r in radii:
            bx, by = xy(longitude, r)
            for shift in shifts:
                x, y = bx + shift * tx, by + shift * ty
                key = (round(x * 10), round(y * 10))
                if key not in seen:
                    seen.add(key)
                    yield x, y

    yield from offer(preferred_radii, preferred_shifts)
    expanded_radii = tuple(range(400, 79, -20))
    expanded_shifts = (0,) + tuple(v for n in range(28, 337, 28) for v in (-n, n))
    yield from offer(expanded_radii, expanded_shifts)


def route(anchor: tuple[float, float], center: tuple[float, float], obstacles: list[Box], diagnostic=None) -> list[tuple[float, float]] | None:
    """Prefer a straight leader; otherwise try deterministic radial elbows.

    A leader is allowed to leave an obstacle that contains its anchor.  This
    is the correct geometry for a body marker lying beneath/adjacent to a
    zodiac label: the leader may escape that local label, but after it has
    exited it may not cross that obstacle again.
    """
    def hits(a, b, obstacle):
        # If the segment begins inside the padded obstacle, ignore only the
        # initial escape through that same obstacle.  Test the remainder after
        # the first exit, so a route that later re-enters is still rejected.
        pad = 8
        inside = (
            obstacle.left - pad <= a[0] <= obstacle.right + pad and
            obstacle.top - pad <= a[1] <= obstacle.bottom + pad
        )
        if not inside:
            return segment_hits_box(a, b, obstacle, pad)
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

    straight_blockers = [
        i for i, b in enumerate(obstacles)
        if hits(anchor, center, b)
    ]
    if not straight_blockers:
        return [anchor, center]
    if diagnostic is not None:
        diagnostic["straight_blocked"] = diagnostic.get("straight_blocked", 0) + 1
        for i in straight_blockers:
            key = f"obstacle_{i}"
            diagnostic["straight_blockers"][key] = diagnostic["straight_blockers"].get(key, 0) + 1

    ax, ay = anchor
    for r in (395, 365, 335, 305, 275, 245, 215, 185, 155):
        lon = math.degrees(math.atan2(-(ay - CY), ax - CX)) - 180
        ex, ey = xy(lon, r)
        first_blockers = [
            i for i, b in enumerate(obstacles)
            if hits(anchor, (ex, ey), b)
        ]
        second_blockers = [
            i for i, b in enumerate(obstacles)
            if hits((ex, ey), center, b)
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
    for r in (395, 365, 335, 305, 275, 245, 215, 185, 155):
        e1 = xy(lon, r)
        for shift in (70, -70, 105, -105, 140, -140, 175, -175, 210, -210, 245, -245, 280, -280, 315, -315):
            e2 = (e1[0] + shift * tx, e1[1] + shift * ty)
            first_blocked = any(hits(anchor, e1, b) for b in obstacles)
            second_blocked = any(hits(e1, e2, b) for b in obstacles)
            third_blocked = any(hits(e2, center, b) for b in obstacles)
            if not first_blocked and not second_blocked and not third_blocked:
                if diagnostic is not None:
                    diagnostic["dogleg_success"] = diagnostic.get("dogleg_success", 0) + 1
                return [anchor, e1, e2, center]
    if diagnostic is not None:
        diagnostic["dogleg_failed"] = diagnostic.get("dogleg_failed", 0) + 1
        diagnostic["route_failed"] = diagnostic.get("route_failed", 0) + 1
    return None


def _solve_order(mode: str, bodies, order, budget):
    """Solve one placement pass, choosing the most constrained body at each level."""
    reserved = reserved_boxes(mode)
    reserved_names = ["center_title", "center_direction", "center_sector_note", *[f"zodiac_{name}" for _, name in SIGNS]]
    staged = {}
    placed: list[Box] = []
    leaders: list[list[tuple[float, float]]] = []
    nodes = 0
    max_nodes = 1_000_000
    started = time.monotonic()
    last_heartbeat = started
    candidates = 0
    rejected_overlap = 0
    rejected_leader = 0
    rejected_route = 0
    backtracks = 0
    deepest = 0
    current_body = "-"
    diagnostic_stats = {}
    route_diagnostics = {}
    body_choice_attempts = {}
    zero_viable_events = {}
    last_ranked = []

    def dump_diagnostics(reason):
        print(
            f"Planet Finder {mode}: TERMINAL reason={reason} nodes={nodes:,} "
            f"deepest={deepest}/{len(order)} current_body={current_body} "
            f"candidates={candidates:,} global_candidates={budget['candidates']:,}/"
            f"{budget['max_candidates']:,} rejects[overlap={rejected_overlap:,},"
            f"leader={rejected_leader:,},route={rejected_route:,}] backtracks={backtracks:,}",
            flush=True,
        )
        if last_ranked:
            print(
                "Planet Finder " + mode + ": TERMINAL last-ranking " +
                ", ".join(f"{name}:{count}" for name, count in last_ranked),
                flush=True,
            )
        for (depth, name), count in sorted(zero_viable_events.items()):
            print(
                f"Planet Finder {mode}: TERMINAL zero-viable depth={depth} "
                f"body={name} occurrences={count:,}", flush=True,
            )
        for (depth, name), s in sorted(diagnostic_stats.items()):
            accounted = s["viable"] + s["overlap"] + s["leader"] + s["route"]
            print(
                f"Planet Finder {mode}: TERMINAL body depth={depth} body={name} "
                f"generated={s['generated']:,} viable={s['viable']:,} "
                f"rejects[overlap={s['overlap']:,},leader={s['leader']:,},route={s['route']:,}] "
                f"accounted={accounted:,}/{s['generated']:,}", flush=True,
            )

    def viable_candidates(item, depth):
        """Materialize currently viable placements for one remaining body."""
        original_index, (symbol, name, longitude) = item
        key = (depth, name)
        stats = diagnostic_stats.setdefault(key, {
            "generated": 0, "viable": 0, "overlap": 0, "leader": 0, "route": 0,
        })
        nonlocal candidates, rejected_overlap, rejected_leader, rejected_route
        w, h = label_size(mode, name)
        anchor = xy(longitude, RI - 5)
        viable = []
        for x, y in candidate_positions(longitude):
            candidates += 1
            stats["generated"] += 1
            budget["candidates"] += 1
            if budget["candidates"] > budget["max_candidates"]:
                dump_diagnostics("candidate budget exhausted")
                raise RuntimeError(
                    f"Planet Finder candidate budget exhausted in {mode} mode "
                    f"after {budget['max_candidates']:,} candidate evaluations"
                )
            box = Box(x, y, w, h)
            if any(boxes_overlap(box, b, 14) for b in reserved + placed):
                rejected_overlap += 1
                stats["overlap"] += 1
                continue
            if any(segment_hits_box(seg[i], seg[i + 1], box, 10)
                   for seg in leaders for i in range(len(seg) - 1)):
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
            path = route(anchor, (x, y), reserved + placed, route_diag)
            if path is None:
                rejected_route += 1
                stats["route"] += 1
                continue
            stats["viable"] += 1
            viable.append((box, path))
        return viable

    def solve(remaining) -> bool:
        nonlocal nodes, last_heartbeat, backtracks, deepest, current_body
        nodes += 1
        position = len(order) - len(remaining)
        deepest = max(deepest, position)
        now = time.monotonic()
        if now - last_heartbeat >= 5:
            elapsed = now - started
            rate = nodes / elapsed if elapsed else 0
            print(
                f"Planet Finder {mode}: heartbeat elapsed={elapsed:.1f}s "
                f"nodes={nodes:,} ({rate:,.0f}/s) depth={position}/{len(order)} "
                f"body={current_body} candidates={candidates:,} "
                f"rejects[overlap={rejected_overlap:,},leader={rejected_leader:,},route={rejected_route:,}] "
                f"backtracks={backtracks:,}",
                flush=True,
            )
            last_heartbeat = now
        if nodes > max_nodes:
            dump_diagnostics("recursive-node budget exhausted")
            raise RuntimeError(
                f"Planet Finder search budget exhausted in {mode} mode "
                f"after {max_nodes:,} recursive nodes"
            )
        if not remaining:
            return True

        # Squeaky wheel gets the grease: measure every remaining body against
        # the current partial layout.  Try the most constrained body first, but
        # body choice itself is part of the backtracking search: if all of that
        # body's placements fail deeper down, try the next-most-constrained body.
        ranked = []
        for rank, item in enumerate(remaining):
            options = viable_candidates(item, position)
            ranked.append((len(options), rank, item, options))
        ranked.sort(key=lambda row: (row[0], row[1]))
        last_ranked[:] = [(row[2][1][1], row[0]) for row in ranked]
        print(
            f"Planet Finder {mode}: ranking depth={position} " +
            ", ".join(f"{name}={count}" for name, count in last_ranked),
            flush=True,
        )

        # A body with no viable placement makes this partial layout impossible;
        # changing which other body is selected next cannot restore free space.
        if ranked[0][0] == 0:
            current_body = ranked[0][2][1][1]
            s = diagnostic_stats[(position, current_body)]
            zero_key = (position, current_body)
            zero_viable_events[zero_key] = zero_viable_events.get(zero_key, 0) + 1
            accounted = s["viable"] + s["overlap"] + s["leader"] + s["route"]
            print(
                f"Planet Finder {mode}: dead end depth={position}/{len(order)} "
                f"body={current_body} generated={s['generated']:,} viable={s['viable']:,} "
                f"rejects[overlap={s['overlap']:,},leader={s['leader']:,},route={s['route']:,}] "
                f"accounted={accounted:,}/{s['generated']:,}",
                flush=True,
            )
            backtracks += 1
            return False

        for _, chosen_rank, chosen, options in ranked:
            original_index, (symbol, name, longitude) = chosen
            current_body = name
            choice_key = (position, name)
            body_choice_attempts[choice_key] = body_choice_attempts.get(choice_key, 0) + 1
            next_remaining = remaining[:chosen_rank] + remaining[chosen_rank + 1:]

            for box, path in options:
                placed.append(box)
                leaders.append(path)
                staged[original_index] = (symbol, name, longitude, box, path)
                if solve(next_remaining):
                    return True
                del staged[original_index]
                leaders.pop()
                placed.pop()
                backtracks += 1
        return False

    try:
        solved = solve(order)
    except Exception as exc:
        dump_diagnostics(f"exception {type(exc).__name__}: {exc}")
        raise
    elapsed = time.monotonic() - started
    print(
        f"Planet Finder {mode}: dynamic-search summary solved={solved} "
        f"elapsed={elapsed:.2f}s nodes={nodes:,} deepest={deepest}/{len(order)} "
        f"candidates={candidates:,} rejects[overlap={rejected_overlap:,},"
        f"leader={rejected_leader:,},route={rejected_route:,}] backtracks={backtracks:,}",
        flush=True,
    )
    for (depth, name), count in sorted(body_choice_attempts.items()):
        print(
            f"Planet Finder {mode}: body-choice depth={depth} body={name} attempts={count:,}",
            flush=True,
        )
    for (depth, name), s in sorted(diagnostic_stats.items()):
        accounted = s["viable"] + s["overlap"] + s["leader"] + s["route"]
        print(
            f"Planet Finder {mode}: diagnostic depth={depth} body={name} "
            f"generated={s['generated']:,} viable={s['viable']:,} "
            f"rejects[overlap={s['overlap']:,},leader={s['leader']:,},route={s['route']:,}] "
            f"accounted={accounted:,}/{s['generated']:,}",
            flush=True,
        )
    for (depth, name), d in sorted(route_diagnostics.items()):
        if d["route_failed"] == 0:
            continue
        straight = ",".join(
            f"{d['obstacle_names'][int(k.split('_')[1])]}:{v}" for k, v in sorted(d["straight_blockers"].items())
        ) or "-"
        print(
            f"Planet Finder {mode}: route diagnostic depth={depth} body={name} "
            f"straight_blocked={d['straight_blocked']:,} route_failed={d['route_failed']:,} "
            f"straight_blockers[{straight}]",
            flush=True,
        )
        for r, legs in d["elbows"].items():
            first = ",".join(f"{d['obstacle_names'][int(k.split('_')[1])]}:{v}" for k, v in sorted(legs["first"].items())) or "-"
            second = ",".join(f"{d['obstacle_names'][int(k.split('_')[1])]}:{v}" for k, v in sorted(legs["second"].items())) or "-"
            print(
                f"Planet Finder {mode}: route elbow depth={depth} body={name} r={r} "
                f"first[{first}] second[{second}]",
                flush=True,
            )
    if not solved:
        dump_diagnostics("search space exhausted without a complete layout")
        return False, None
    return True, [staged[i] for i in range(len(bodies))]


def layout(mode: str, bodies: list[tuple[str, str, float]]):
    """Find a collision-free layout with dynamic body-order backtracking.

    Canonical order is retained only as the deterministic tie-break order.
    At every recursion level the solver measures all remaining bodies, tries
    the most constrained first, and can backtrack over both placement and body
    choice.  There is therefore no outer "first body" retry loop.
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

    budget = {"candidates": 0, "max_candidates": 1_000_000}
    print(
        f"Planet Finder {mode}: starting dynamic body-order and placement search",
        flush=True,
    )
    solved, result = _solve_order(mode, bodies, indexed, budget)
    if solved:
        print(
            f"Planet Finder {mode}: solved by dynamic body-order backtracking",
            flush=True,
        )
        return result

    raise RuntimeError(
        f"No collision-free Planet Finder layout exists in {mode} mode after "
        f"dynamic body-order and placement backtracking"
    )

def polyline(points):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{pts}" fill="none" stroke="#777" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'


def render(year: int, week: int, monday: date, mode: str, bodies: list[tuple[str, str, float]]) -> str:
    labels = {"greek": "Greek / Symbols", "latin": "Latin", "mixed": "Mixed / Learner"}
    title = labels[mode]
    placed = layout(mode, bodies)
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
    out.append('<text x="250" y="708" text-anchor="end" font-size="20" class="sans">0° Aries</text>')

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