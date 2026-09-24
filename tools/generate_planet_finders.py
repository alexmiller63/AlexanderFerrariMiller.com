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
from almanack_paths import week_dir
from planet_finder_search import DepthNodeBudgetExhausted, SearchOutcome, new_search_budget, layout, diagnostic_print
from planet_finder_validation import validate_layout
from planet_finder_rendering import polyline, render
from planet_finder_geometry import (
    W, H, CX, CY, RO, RI,
    LABEL_RIM_CLEARANCE, LABEL_COLLISION_PADDING,
    IMMUTABLE_LEADER_CLEARANCE, PLACED_LABEL_LEADER_CLEARANCE,
    LEADER_TO_LEADER_CLEARANCE, LEADER_RIM_CLEARANCE,
    LABEL_LENGTH, PREFERRED_LABEL_RADII, EXPANDED_LABEL_RADII, ROUTE_RADII,
    SIGNS, BODY_SYMBOLS, BODY_NAMES, CANONICAL,
    DEFAULT_CANDIDATE_LAYOUTS, DEFAULT_MAX_NODE_CANDIDATES,
    DEFAULT_MAX_SEARCH_SECONDS,
    FinderMode, Body, Box,
    xy, boxes_overlap, segment_hits_box, point_segment_distance,
    segments_too_close, leaders_too_close, leader_hits_zodiac_rim,
    label_size, reserved_boxes, candidate_positions,
    legal_candidate_positions, route,
)

ROOT = Path(__file__).resolve().parents[1]
def _solve_order(mode: str, bodies, order, budget, target_solutions=5, order_index=1, total_orders=None, context_label=None, displacement_scale=2.0, body_attempts=None, refinement_deadline=None):
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
    # One authoritative cap per body for this mode. It counts viable
    # candidates admitted to DFS for each body; rejected raw proposals and
    # forward-check witnesses do not consume it. The count persists when the
    # controller changes ordering, so reordering can never replenish a body's
    # 200-candidate safety budget.
    if body_attempts is None:
        body_attempts = {name: 0 for _, (_, name, _) in order}
    diagnostic_stats = {}
    route_diagnostics = {}
    solutions = []
    solution_keys = set()
    contest_keys = []
    current_body = "-"
    exhausted = False
    def dump_diagnostics(reason):
        # A capped ordering is expected control flow, not a terminal failure.
        # Emit one compact summary for it; full forensic dumps are reserved
        # for genuinely terminal/exhausted searches. This keeps legitimate
        # ordering exploration from exhausting the GitHub Actions log.
        if reason.startswith("body-attempt-cap"):
            order_names = " > ".join(item[1][1] for item in order)
            diagnostic_print(
                f"Planet Finder {mode}: CAPPED SUMMARY order={order_index} "
                f"nodes={nodes:,} deepest={deepest}/{len(order)} "
                f"current_body={current_body} sequence={order_names}",
                flush=True,
            )
            return
        order_names = " > ".join(item[1][1] for item in order)
        diagnostic_print(
            f"Planet Finder {mode}: TERMINAL {context_label + ' ' if context_label else ''}reason={reason} order={order_index}"
            f"{('/' + str(total_orders)) if total_orders else ''} "
            f"nodes={nodes:,} deepest={deepest}/{len(order)} current_body={current_body} "
            f"candidates={candidates:,} rejects[overlap={rejected_overlap:,},"
            f"leader={rejected_leader:,},route={rejected_route:,}] "
            f"backtracks={backtracks:,}",
            flush=True,
        )
        diagnostic_print(f"Planet Finder {mode}: TERMINAL ORDER sequence={order_names}", flush=True)
        for (depth, name), s in sorted(diagnostic_stats.items()):
            immutable_names = {
                reserved_names[i] if i < len(reserved_names) else str(i): count
                for i, count in sorted(s.get("immutable_reserved_by_obstacle", {}).items())
            }
            diagnostic_print(
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
        for (depth, name), s in sorted(diagnostic_stats.items()):
            for candidate_index, audit in enumerate(s.get("immutable_candidate_audit", []), 1):
                x, y, rejection, obstacle_ids = audit
                obstacle_labels = [reserved_names[i] if i < len(reserved_names) else str(i) for i in obstacle_ids]
                diagnostic_print(
                    f"Planet Finder {mode}: TERMINAL IMMUTABLE-CANDIDATE "
                    f"depth={depth}/{len(order)} body={name} candidate={candidate_index} "
                    f"center=({x:.1f},{y:.1f}) reason={rejection} obstacles={obstacle_labels}",
                    flush=True,
                )
        for depth in sorted(set(depth_residence) | set(depth_visits)):
            body_name = order[depth][1][1] if depth < len(order) else "complete-layout"
            diagnostic_print(
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
            diagnostic_print(
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
        diagnostic_print(
            f"Planet Finder {mode}: TERMINAL REJECTION CONSTRAINTS "
            + " ".join(f"{key}={count:,}" for key, count in ranked),
            flush=True,
        )
        diagnostic_print(
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
            # The cap is owned by the body, not by this generator instance or
            # this ordering. A body already at its persistent limit must not
            # receive one additional candidate merely because its ordering
            # changed.
            if body_attempts[name] >= budget["max_node_candidates"]:
                stats["blocked"] = "body-candidate-cap"
                diagnostic_print(
                    f"Planet Finder {mode}: BODY-CANDIDATE CAP order={order_index} "
                    f"depth={depth}/{len(order)} body={name} "
                    f"viable={body_attempts[name]:,}/{budget['max_node_candidates']:,}",
                    flush=True,
                )
                raise DepthNodeBudgetExhausted(depth, name)

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
                diagnostic_print(
                    f"Planet Finder {mode}: SLOW candidate-position body={name} "
                    f"depth={depth}/{len(order)} raw={raw_positions:,} dt={stream_dt:.3f}s",
                    flush=True,
                )
            now = time.monotonic()
            if now - candidate_last_heartbeat >= 5.0:
                diagnostic_print(
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
            now = time.monotonic()
            if refinement_deadline is not None and now >= refinement_deadline:
                stats["blocked"] = "refinement-deadline"
                diagnostic_print(
                    f"Planet Finder {mode}: CANDIDATE REFINEMENT DEADLINE "
                    f"order={order_index} depth={depth}/{len(order)} body={name}; "
                    f"returning to controller",
                    flush=True,
                )
                return
            run_elapsed = now - budget["started"]
            if run_elapsed >= budget["max_seconds"]:
                stats["blocked"] = "wall-clock"
                diagnostic_print(
                    f"Planet Finder {mode}: CANDIDATE-GENERATION STOP wall-clock budget exhausted "
                    f"order={order_index} depth={depth}/{len(order)} body={name} "
                    f"after {run_elapsed:.1f}s/{budget['max_seconds']:.1f}s "
                    f"viable={body_candidates:,}",
                    flush=True,
                )
                body_forward = forward_stats["by_body"].get(name, {})
                diagnostic_print(
                    f"Planet Finder {mode}: TIMEOUT-AUDIT order={order_index} "
                    f"body={name} body-attempts={body_attempts.get(name, 0):,} "
                    f"forward[checks={body_forward.get('checks', 0):,},"
                    f"witnesses={body_forward.get('witnesses', 0):,},"
                    f"dead={body_forward.get('dead', 0):,},"
                    f"raw={body_forward.get('raw', 0):,}] "
                    f"totals[checks={forward_stats['checks']:,},"
                    f"witnesses={forward_stats['witnesses']:,},"
                    f"pruned={forward_stats['pruned']:,}] "
                    f"dfs[nodes={nodes:,},deepest={deepest}/{len(order)},"
                    f"candidates={candidates:,},backtracks={backtracks:,}]",
                    flush=True,
                )
                diagnostic_print(
                    f"Planet Finder {mode}: TIMEOUT-BODIES "
                    + " ".join(
                        f"{body}:a={body_attempts.get(body, 0)},"
                        f"fc={forward_stats['by_body'].get(body, {}).get('checks', 0)},"
                        f"fw={forward_stats['by_body'].get(body, {}).get('witnesses', 0)},"
                        f"fd={forward_stats['by_body'].get(body, {}).get('dead', 0)}"
                        for _, (_, body, _) in order
                    ),
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
                diagnostic_print(
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
            # This is the single cap point: only a fully viable candidate
            # admitted to DFS consumes the body's candidate budget.
            body_candidates += 1
            body_attempts[name] += 1
            stats["generated"] += 1
            stats["viable"] += 1
            last_yield_at = time.monotonic()
            yield box, path
            if body_attempts[name] >= budget["max_node_candidates"]:
                stats["blocked"] = "body-candidate-cap"
                diagnostic_print(
                    f"Planet Finder {mode}: BODY-CANDIDATE CAP order={order_index} "
                    f"depth={depth}/{len(order)} body={name} "
                    f"viable={body_attempts[name]:,}/{budget['max_node_candidates']:,}",
                    flush=True,
                )
                raise DepthNodeBudgetExhausted(depth, name)

    forward_stats = {"checks": 0, "pruned": 0, "witnesses": 0, "by_body": {}}

    def forward_check(next_depth):
        """Return False only when a remaining body is already provably dead.

        This is a one-witness feasibility check and does not stage a placement.
        Its probes are diagnostic look-ahead, not DFS contestants, so they do
        not consume the per-body DFS candidate cap. Diagnostics still record
        the amount of look-ahead work and which future bodies receive witnesses.
        """
        obstacles = [*reserved, *placed]
        # Match real DFS exactly: only the 3 fixed center annotations may
        # contain an anchor and permit an initial escape. Zodiac labels never do.
        immutable_count = 3
        forward_stats["checks"] += 1
        for future_depth in range(next_depth, len(order)):
            _, (_, future_name, future_longitude) = order[future_depth]
            w, h = label_size(mode, future_name)
            anchor = xy(future_longitude, RI - 5)
            prefix_cache = {}
            witness = False
            witness_raw = 0
            for _, _, future_box in legal_candidate_positions(
                future_longitude, w, h, reserved, displacement_scale
            ):
                witness_raw += 1
                # Look-ahead stops at the first witness. Count its raw probes
                # only in forward_stats; the 200 cap belongs to actual DFS
                # candidate generation, not speculative feasibility checks.
                if any(boxes_overlap(future_box, other, 14) for other in placed):
                    continue
                center = (future_box.x, future_box.y)
                path = route(
                    anchor,
                    center,
                    obstacles,
                    allow_initial_escape_count=immutable_count,
                    prefix_cache=prefix_cache,
                )
                if path is None:
                    continue
                if leader_hits_zodiac_rim(path):
                    continue
                if leaders_too_close(path, leaders):
                    continue
                witness = True
                break
            body_stat = forward_stats["by_body"].setdefault(
                future_name, {"checks": 0, "witnesses": 0, "dead": 0, "raw": 0}
            )
            body_stat["checks"] += 1
            body_stat["raw"] += witness_raw
            if witness:
                body_stat["witnesses"] += 1
                forward_stats["witnesses"] += 1
            else:
                body_stat["dead"] += 1
                forward_stats["pruned"] += 1
                return False
        return True

    def search(depth):
        """Recursive DFS: each call owns exactly one body depth.

        Geometry rejects bad proposals before they enter this function.
        Returning from a child is the only backtracking mechanism.
        """
        nonlocal nodes, deepest, candidates, backtracks, current_body

        now = time.monotonic()
        if refinement_deadline is not None and now >= refinement_deadline:
            diagnostic_print(
                f"Planet Finder {mode}: DFS REFINEMENT DEADLINE order={order_index} "
                f"depth={depth}/{len(order)} body={current_body}; returning to controller",
                flush=True,
            )
            return False
        run_elapsed = now - budget["started"]
        if run_elapsed >= budget["max_seconds"]:
            diagnostic_print(
                f"Planet Finder {mode}: TIMEOUT-AUDIT order={order_index} "
                f"body={current_body} totals[checks={forward_stats['checks']:,},"
                f"witnesses={forward_stats['witnesses']:,},"
                f"pruned={forward_stats['pruned']:,}] "
                f"dfs[nodes={nodes:,},deepest={deepest}/{len(order)},"
                f"candidates={candidates:,},backtracks={backtracks:,}]",
                flush=True,
            )
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
                    diagnostic_print(
                        f"Planet Finder {mode}: complete valid candidate "
                        f"{len(solutions)}/{target_solutions} "
                        f"order={order_index} placement-order=" +
                        " > ".join(row[1] for row in result),
                        flush=True,
                    )
                else:
                    diagnostic_print(
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
                # Forward checking asks only for one viable witness for every
                # remaining body. Zero proves this prefix is dead; one is
                # enough to preserve it for the real DFS.
                if forward_check(depth + 1) and search(depth + 1):
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
                diagnostic_print(
                    f"Planet Finder {mode}: PREFIX BACKTRACK "
                    f"depth={depth}/{len(order)} body={name} "
                    f"candidate={candidates} "
                    f"child-deepest={deepest}/{len(order)} "
                    f"new-depth={deepest > child_deepest_before} "
                    f"child-nodes={nodes - child_nodes_before} "
                    f"child-backtracks={backtracks - child_backtracks_before}",
                    level=2,
                    flush=True,
                )

        if not generated_here:
            dead_key = (depth, name)
            dead_end_visits[dead_key] = dead_end_visits.get(dead_key, 0) + 1
            # Reuse the same per-body cap: too many candidates in one prefix
            # or too many zero-candidate prefixes both identify a squeaky wheel.
            if dead_end_visits[dead_key] >= budget["max_node_candidates"]:
                diagnostic_print(
                    f"Planet Finder {mode}: REPEATED-DEAD-END STOP order={order_index} "
                    f"depth={depth}/{len(order)} body={name} "
                    f"dead-ends={dead_end_visits[dead_key]:,}/{budget['max_node_candidates']:,}",
                    flush=True,
                )
                raise DepthNodeBudgetExhausted(depth, name)
            stats = diagnostic_stats[(depth, name)]
            diagnostic_print(
                f"Planet Finder {mode}: dead end order={order_index} "
                f"depth={depth}/{len(order)} body={name} "
                f"status={'evaluated' if stats.get('started') else 'not-evaluated'} "
                f"generated={stats['generated']:,} viable={stats['viable']:,} "
                f"rejects[overlap={stats['overlap']:,},leader={stats['leader']:,},"
                f"route={stats['route']:,}]",
                level=2,
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
    diagnostic_print(
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


def generate_week(year: int, week: int):
    if not 1 <= week <= week_count(year):
        raise ValueError(f"Invalid ISO week {year}-W{week:02d}")
    monday = date.fromisocalendar(year, week, 1)
    needed = {BODY_NAMES[name] for name in CANONICAL}
    engine = StarAlmanackEphemeris()
    generated = computed_ephemeris(year, engine)
    values = {key: generated[key][week - 1][0] for key in needed}
    bodies = [(BODY_SYMBOLS[BODY_NAMES[name]], name, values[BODY_NAMES[name]] % 360) for name in CANONICAL]
    outdir = week_dir(year, week) / "finders"
    outdir.mkdir(parents=True, exist_ok=True)
    filenames = {
        FinderMode.GREEK: "planet-finder-greek-symbols.svg",
        FinderMode.LATIN: "planet-finder-latin.svg",
        FinderMode.MIXED: "planet-finder-mixed-learner.svg",
    }
    # Generate the complete 3-mode set in memory first. A failure in any mode
    # must leave the week's published finder set untouched; never publish a
    # partial Greek/Latin/Mixed result.
    rendered = {}
    for mode, filename in filenames.items():
        rendered[filename] = render(year, week, monday, mode, bodies)

    # render()/layout() independently validates every selected layout before it
    # returns. Only after all 3 modes succeed do we replace the week's files.
    for filename, svg in rendered.items():
        (outdir / filename).write_text(svg, encoding="utf-8")
    diagnostic_print(f"Generated collision-free Planet Finders for ISO {year}-W{week:02d} from internal calculations")


def parse_args():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--current", action="store_true", help="generate the current UTC ISO week")
    g.add_argument("--year", type=int, help="ISO week-year")
    p.add_argument("--week", type=int, help="ISO week number; required with --year")
    p.add_argument("--diagnostic-level", type=int, default=None, metavar="N", help="diagnostic verbosity: 0=silent, 1=major events, 2=search detail, 3=forensic detail")
    args = p.parse_args()
    if args.year is not None and args.week is None:
        p.error("--week is required with --year")
    return args


def main():
    args = parse_args()
    if args.diagnostic_level is not None:
        if args.diagnostic_level < 0:
            raise SystemExit("--diagnostic-level must be zero or greater")
        os.environ["PLANET_FINDER_DIAGNOSTIC_LEVEL"] = str(args.diagnostic_level)
    if args.current:
        today = date.today()
        iso = today.isocalendar()
        year, week = iso.year, iso.week
    else:
        year, week = args.year, args.week
    generate_week(year, week)


if __name__ == "__main__":
    main()