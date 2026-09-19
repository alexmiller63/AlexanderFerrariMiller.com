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


def _permutation_by_rank(items, rank: int):
    """Return one lexicographic permutation without recursive generation."""
    pool = list(items)
    result = []
    for size in range(len(pool), 0, -1):
        block = math.factorial(size - 1)
        choice, rank = divmod(rank, block)
        result.append(pool.pop(choice))
    return result


def _planned_order_ranks(total: int):
    """Yield widely separated permutation ranks deterministically.

    The first probes are deliberately far apart: canonical, reverse, midpoint,
    quarter points, then a full-cycle modular walk.  This avoids the old
    behavior where a failed ordering was followed by a nearly identical
    ordering.  The sequence is iterative and can eventually cover every
    permutation rank.
    """
    if total <= 0:
        return
    seen = set()
    initial = (0, total - 1, total // 2, total // 4, (3 * total) // 4)
    for rank in initial:
        if rank not in seen:
            seen.add(rank)
            yield rank

    # Coprime with 11! so this modular walk eventually visits every rank.
    step = 19_958_401
    rank = 0
    while len(seen) < total:
        rank = (rank + step) % total
        if rank not in seen:
            seen.add(rank)
            yield rank


def _solve_order(mode: str, bodies, order, budget, target_solutions=5, order_index=1, total_orders=None, context_label=None):
    """Solve one fixed body ordering with an explicit iterative DFS.

    The ordering is fixed for this pass.  Placement backtracking is represented
    by an explicit stack of frames rather than recursive calls.  When the
    ordering is exhausted, the caller selects a deliberately distant ordering.
    """
    reserved = reserved_boxes(mode)
    reserved_names = ["center_title", "center_direction", "center_sector_note",
                      *[f"zodiac_{name}" for _, name in SIGNS]]
    placed: list[Box] = []
    leaders: list[list[tuple[float, float]]] = []
    staged = {}
    stack = []
    nodes = 0
    started = time.monotonic()
    last_heartbeat = started
    candidates = 0
    rejected_overlap = 0
    rejected_leader = 0
    rejected_route = 0
    backtracks = 0
    deepest = 0
    diagnostic_stats = {}
    route_diagnostics = {}
    solutions = []
    solution_keys = set()
    current_body = "-"
    exhausted = False
    ornery_limit = max(1, int(os.environ.get("PLANET_FINDER_ORNERY_CANDIDATES", "50")))
    max_order_nodes = max(1, int(os.environ.get("PLANET_FINDER_MAX_ORDER_NODES", "100000")))
    max_order_seconds = max(1.0, float(os.environ.get("PLANET_FINDER_MAX_ORDER_SECONDS", "5")))

    def dump_diagnostics(reason):
        order_names = " > ".join(item[1][1] for item in order)
        active = []
        for depth, frame in enumerate(stack):
            _, (_, frame_name, _) = frame["item"]
            active.append(
                f"{depth}:{frame_name}[option={frame['index'] + 1}/{len(frame['options'])},"
                f"selected={'yes' if frame.get('selected') is not None else 'no'}]"
            )
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
        print(
            "Planet Finder "
            f"{mode}: TERMINAL STACK " + (" | ".join(active) if active else "(empty)"),
            flush=True,
        )
        for (depth, name), s in sorted(diagnostic_stats.items()):
            print(
                f"Planet Finder {mode}: TERMINAL BODY depth={depth}/{len(order)} body={name} "
                f"status={'evaluated' if s.get('started') else ('blocked-' + s['blocked'] if s.get('blocked') else 'not-evaluated')} "
                f"generated={s['generated']:,} viable={s['viable']:,} "
                f"rejects[overlap={s['overlap']:,},leader={s['leader']:,},route={s['route']:,}]",
                flush=True,
            )
        partial = [
            f"{depth}:{frame['item'][1][1]}"
            for depth, frame in enumerate(stack)
            if frame.get("selected") is not None
        ]
        print(
            f"Planet Finder {mode}: TERMINAL BEST-PARTIAL deepest={deepest}/{len(order)} "
            f"active-depth={len(partial)} placements="
            + (" > ".join(partial) if partial else "(none)"),
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
        viable = []
        body_candidates = 0
        for x, y in candidate_positions(longitude):
            if body_candidates >= ornery_limit:
                print(
                    f"Planet Finder {mode}: ORNERY order={order_index} "
                    f"depth={depth}/{len(order)} body={name} "
                    f"generated={body_candidates:,} viable=0 limit={ornery_limit:,} "
                    f"action=backtrack",
                    flush=True,
                )
                break
            # Share the *remaining* global budget across the current and
            # later DFS depths.  The old rule reserved a full ornery_limit for
            # every later depth against the original global cap.  Once the run
            # had used enough candidates, that reserve could equal/exceed all
            # remaining capacity and every new ordering became "not-evaluated".
            #
            # Reserve only a proportional share of what is actually left.
            # This guarantees the current body a non-zero working allowance
            # whenever any global budget remains, while still preserving work
            # for later depths.
            remaining_depths = len(order) - depth - 1
            remaining_budget = budget["max_candidates"] - budget["candidates"]
            if remaining_budget <= 0:
                stats["blocked"] = "global-budget"
                print(
                    f"Planet Finder {mode}: BUDGET-EXHAUSTED order={order_index} "
                    f"depth={depth}/{len(order)} body={name} "
                    f"used={budget['candidates']:,}/{budget['max_candidates']:,} "
                    f"action=stop",
                    flush=True,
                )
                break
            depths_including_current = remaining_depths + 1
            current_allowance = max(1, remaining_budget // depths_including_current)
            current_allowance = min(ornery_limit, current_allowance)
            if body_candidates >= current_allowance:
                reserved_for_later = remaining_budget - body_candidates
                print(
                    f"Planet Finder {mode}: BUDGET-SHARE order={order_index} "
                    f"depth={depth}/{len(order)} body={name} "
                    f"used={budget['candidates']:,}/{budget['max_candidates']:,} "
                    f"body-used={body_candidates:,} allowance={current_allowance:,} "
                    f"reserved-after-share={reserved_for_later:,} "
                    f"remaining-depths={remaining_depths} action=backtrack",
                    flush=True,
                )
                break
            stats["started"] = True
            candidates += 1
            body_candidates += 1
            stats["generated"] += 1
            budget["candidates"] += 1
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

    def clear_selected(frame):
        """Remove the placement owned by one active DFS frame."""
        selected = frame.get("selected")
        if selected is None:
            return
        original_index = selected[0]
        staged.pop(original_index, None)
        if leaders:
            leaders.pop()
        if placed:
            placed.pop()
        frame["selected"] = None

    def log_heartbeat(position):
        nonlocal last_heartbeat
        now = time.monotonic()
        if now - last_heartbeat < 5:
            return
        elapsed = now - started
        rate = nodes / elapsed if elapsed else 0
        run_started = budget.get("started", started)
        run_elapsed = now - run_started
        run_rate = budget["candidates"] / run_elapsed if run_elapsed else 0
        run_remaining = max(0, budget["max_candidates"] - budget["candidates"])
        run_percent = 100.0 * budget["candidates"] / budget["max_candidates"]
        run_eta = run_remaining / run_rate if run_rate > 0 else float("inf")
        eta_text = f"{run_eta:.0f}s" if math.isfinite(run_eta) else "unknown"
        print(
            f"Planet Finder {mode}: heartbeat {context_label + ' ' if context_label else ''}"
            f"elapsed={elapsed:.1f}s run-elapsed={run_elapsed:.1f}s "
            f"order={order_index}{('/' + str(total_orders)) if total_orders else ''} "
            f"nodes={nodes:,} ({rate:,.0f}/s) depth={position}/{len(order)} "
            f"body={current_body} candidates={candidates:,} "
            f"RUN={budget['candidates']:,}/{budget['max_candidates']:,} "
            f"({run_percent:.1f}%) remaining={run_remaining:,} "
            f"rate={run_rate:,.0f}/s eta={eta_text} "
            f"rejects[overlap={rejected_overlap:,},leader={rejected_leader:,},"
            f"route={rejected_route:,}] backtracks={backtracks:,}",
            flush=True,
        )
        last_heartbeat = now

    # After emitting a complete candidate, resume at the final frame so
    # that frame can try its next placement.  Recomputing position solely from
    # len(stack) would incorrectly produce position == len(order) with an
    # unselected final frame and then index order[position].
    resume_position = None

    while True:
        # Enforce the shared run-wide wall-clock deadline inside the DFS loop.
        # Merely storing max_seconds in the budget is not sufficient: every
        # fixed ordering must cooperatively stop once the generator deadline
        # has expired.
        run_elapsed = time.monotonic() - budget["started"]
        if run_elapsed >= budget["max_seconds"]:
            dump_diagnostics("run-wide wall-clock budget exhausted")
            raise RuntimeError(
                f"Planet Finder run-wide wall-clock budget exhausted in {mode} mode "
                f"after {run_elapsed:.1f}s (limit {budget['max_seconds']:.1f}s)"
            )
        order_elapsed = time.monotonic() - started
        run_elapsed = time.monotonic() - budget["started"]
        if run_elapsed >= budget["max_seconds"]:
            dump_diagnostics("run time budget exhausted")
            raise RuntimeError(
                f"Planet Finder run-wide time budget exhausted in {mode} mode "
                f"after {run_elapsed:.1f}s (limit {budget['max_seconds']:.1f}s)"
            )
        if nodes >= max_order_nodes or order_elapsed >= max_order_seconds:
            reason = (
                f"order node budget exhausted ({nodes:,}/{max_order_nodes:,})"
                if nodes >= max_order_nodes
                else f"order time budget exhausted ({order_elapsed:.1f}s/{max_order_seconds:.1f}s)"
            )
            dump_diagnostics(reason)
            exhausted = True
            break

        if resume_position is None:
            position = len(stack)
        else:
            position = resume_position
            resume_position = None
        deepest = max(deepest, position)
        nodes += 1
        log_heartbeat(position)

        if position == len(order) and all(frame.get("selected") is not None for frame in stack):
            # A complete depth is valid only when every active frame still owns
            # its placement. After a complete candidate is emitted, the final
            # frame is cleared and its index is advanced but deliberately kept
            # on the stack so its next candidate can be tried. Without this
            # invariant guard, the loop re-entered the complete-depth branch
            # with an empty final frame and reported false state corruption.
            missing = [i for i in range(len(bodies)) if i not in staged]
            if missing:
                raise RuntimeError(
                    f"Planet Finder DFS state corruption in {mode}: "
                    f"complete depth but missing staged indices {missing}; "
                    f"stack={len(stack)}"
                )
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
                    if len(solutions) >= target_solutions:
                        break
                else:
                    print(
                        f"Planet Finder {mode}: rejected complete layout "
                        f"order={order_index} errors=" + "; ".join(errors),
                        flush=True,
                    )

            # Keep the final frame alive and resume it at its next option.
            # This is the ordinary DFS "next sibling" transition; it must not
            # recompute position as len(stack), because that would be one past
            # the last valid order index.
            final_position = len(stack) - 1
            clear_selected(stack[final_position])
            stack[final_position]["index"] += 1
            backtracks += 1
            resume_position = final_position
            continue

        # Never index the fixed order at its sentinel depth.  A complete
        # placement is handled above; any other arrival at depth == len(order)
        # means the final frame has been left without a selected placement.
        # Recover explicitly to the final frame instead of allowing
        # order[position] to raise IndexError.  This is also instrumented so a
        # future DFS-state regression is visible in the workflow log.
        if position >= len(order):
            if position > len(order):
                raise RuntimeError(
                    f"Planet Finder DFS state corruption in {mode}: "
                    f"position={position} exceeds order depth {len(order)}; "
                    f"stack={len(stack)}"
                )
            if not stack:
                raise RuntimeError(
                    f"Planet Finder DFS state corruption in {mode}: "
                    f"sentinel depth with empty stack"
                )
            print(
                f"Planet Finder {mode}: DFS sentinel recovery "
                f"order={order_index} depth={position}/{len(order)} "
                f"selected={[frame.get('selected') is not None for frame in stack]}",
                flush=True,
            )
            position = len(order) - 1
            resume_position = position
            continue

        if len(stack) == position:
            item = order[position]
            options = viable_candidates(item, position)
            stack.append({
                "item": item,
                "options": options,
                "index": 0,
                "selected": None,
            })
            if not options:
                original_index, (_, name, _) = item
                current_body = name
                s = diagnostic_stats[(position, name)]
                print(
                    f"Planet Finder {mode}: dead end order={order_index} "
                    f"depth={position}/{len(order)} body={name} "
                    f"status={'evaluated' if s.get('started') else 'not-evaluated'} "
                    f"generated={s['generated']:,} viable={s['viable']:,} "
                    f"rejects[overlap={s['overlap']:,},leader={s['leader']:,},"
                    f"route={s['route']:,}]",
                    flush=True,
                )
                stack.pop()
                if position == 0:
                    exhausted = True
                    break
                position -= 1
                clear_selected(stack[position])
                stack[position]["index"] += 1
                backtracks += 1
                continue

        frame = stack[position]
        if frame["index"] >= len(frame["options"]):
            # This frame has tried every candidate. Remove its own placement,
            # then return control to its parent without disturbing the parent.
            clear_selected(frame)
            stack.pop()
            if position == 0:
                exhausted = True
                break
            parent = stack[position - 1]
            clear_selected(parent)
            parent["index"] += 1
            backtracks += 1
            continue

        original_index, (symbol, name, longitude) = frame["item"]
        current_body = name
        box, path = frame["options"][frame["index"]]
        placed.append(box)
        leaders.append(path)
        staged[original_index] = (symbol, name, longitude, box, path)
        frame["selected"] = (original_index, (symbol, name, longitude, box, path))

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
    """Create the shared candidate and wall-clock budget for one complete generator run."""
    if max_candidates is None:
        max_candidates = int(os.environ.get("PLANET_FINDER_MAX_CANDIDATES", "1000000"))
    if max_candidates <= 0:
        raise ValueError("PLANET_FINDER_MAX_CANDIDATES must be positive")
    max_seconds = max(1.0, float(os.environ.get("PLANET_FINDER_MAX_SECONDS", "90")))
    # Start the wall-clock budget lazily at the first actual layout search.
    # Ephemeris setup/kernel work must not consume the Planet Finder search ceiling.
    return {
        "candidates": 0,
        "max_candidates": max_candidates,
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
    """Search widely separated body orderings with iterative placement DFS.

    The canonical order is always the first ordering.  If that ordering cannot
    supply the requested candidates, the next ordering is deliberately far away
    in permutation space.  The search eventually covers all 11! orderings,
    subject to the shared 1,000,000 candidate-evaluation cap.
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

    total_orders = math.factorial(len(indexed))
    if budget is None:
        budget = new_search_budget()
    if budget.get("started") is None:
        budget["started"] = time.monotonic()
        print(
            f"Planet Finder SEARCH CLOCK STARTED: limit={budget['max_seconds']:.1f}s",
            flush=True,
        )
    all_solutions = []
    seen_solution_keys = set()

    print(
        f"Planet Finder {mode}: starting planned-order iterative search "
        f"{context_label + ' ' if context_label else ''}"
        f"target={target_solutions} max-candidates={budget['max_candidates']:,} "
        f"permutation-space={total_orders:,}",
        flush=True,
    )

    for order_index, rank in enumerate(_planned_order_ranks(total_orders), start=1):
        order = _permutation_by_rank(indexed, rank)
        order_names = " > ".join(item[1][1] for item in order)
        print(
            f"Planet Finder {mode}: ORDER {order_index} rank={rank:,}/{total_orders:,} "
            f"run-candidates={budget['candidates']:,}/{budget['max_candidates']:,} "
            f"sequence={order_names}",
            flush=True,
        )

        solutions = _solve_order(
            mode,
            bodies,
            order,
            budget,
            target_solutions=max(1, target_solutions - len(all_solutions)),
            order_index=order_index,
            total_orders=total_orders,
            context_label=context_label,
        )
        for result in solutions:
            key = tuple(
                (
                    row[1],
                    round(row[3].x, 3),
                    round(row[3].y, 3),
                    tuple((round(x, 3), round(y, 3)) for x, y in row[4]),
                )
                for row in result
            )
            if key not in seen_solution_keys:
                seen_solution_keys.add(key)
                all_solutions.append(result)
                if len(all_solutions) >= target_solutions:
                    break

        if len(all_solutions) >= target_solutions:
            print(
                f"Planet Finder {mode}: target reached with {len(all_solutions)} "
                f"unique candidates after {order_index} planned orderings",
                flush=True,
            )
            break

    if not all_solutions:
        raise RuntimeError(
            f"No collision-free Planet Finder layout found in {mode} mode after "
            f"{budget['candidates']:,} candidate evaluations across planned orderings"
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
    return "
".join(out) + "
"


def generate_week(
    year: int,
    week: int,
    budget: dict | None = None,
    context_label: str | None = None,
):
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
        (outdir / filename).write_text(
            render(
                year, week, monday, mode, bodies,
                budget=budget,
                context_label=context_label,
            ),
            encoding="utf-8",
        )
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