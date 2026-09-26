"""Planet Finder search support.

This module is being extracted incrementally from generate_planet_finders.py.
Keep changes behavior-preserving and validate each extraction before moving
additional search machinery here.
"""

from __future__ import annotations

from dataclasses import dataclass

from planet_finder_validation import validate_layout
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
    segments_too_close, leaders_too_close, leader_hits_zodiac_rim, minimum_leader_separation,
    label_size, reserved_boxes, candidate_positions,
    legal_candidate_positions, route, alignment_groups, conjunction_groups, conjunction_glyph_radii,
)


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

import math
import os
import time



_DIAGNOSTIC_LEVEL = int(os.environ.get("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1"))


def diagnostic_print(*args, level=None, **kwargs):
    """Print Planet Finder diagnostics at the configured verbosity level.

    Level 0 is silent. Level 1 shows major controller events. Level 2 adds
    search-order and contest detail. Level 3 adds forensic terminal detail.
    Higher levels currently include all diagnostics.
    """
    try:
        configured = max(0, int(os.environ.get("PLANET_FINDER_DIAGNOSTIC_LEVEL", str(_DIAGNOSTIC_LEVEL))))
    except ValueError:
        configured = 1
    if level is None:
        text = " ".join(str(arg) for arg in args)
        if any(token in text for token in ("TERMINAL BODY", "IMMUTABLE-CANDIDATE", "HEARTBEAT")):
            level = 3
        elif any(token in text for token in ("CONTESTANT", "squeaky-wheel", "PROMOTE", "CAPPED", "REFINEMENT", "SEARCH OUTCOME")):
            level = 2
        else:
            level = 1
    if configured >= level:
        print(*args, **kwargs)

from planet_finder_geometry import (
    CANONICAL, FinderMode, CX, CY, xy,
    DEFAULT_CANDIDATE_LAYOUTS, DEFAULT_MAX_NODE_CANDIDATES,
    DEFAULT_MAX_SEARCH_SECONDS,
)

def new_search_budget():
    """Create the per-body candidate and wall-clock safety limits."""
    max_node_candidates = int(os.environ.get("PLANET_FINDER_MAX_NODE_CANDIDATES", str(DEFAULT_MAX_NODE_CANDIDATES)))
    if max_node_candidates <= 0:
        raise ValueError("PLANET_FINDER_MAX_NODE_CANDIDATES must be positive")
    max_seconds = max(1.0, float(os.environ.get("PLANET_FINDER_MAX_SECONDS", str(DEFAULT_MAX_SEARCH_SECONDS))))
    # This object contains limits only.  It deliberately contains no clock
    # state: every notation mode starts its own clock inside layout().
    return {
        "max_node_candidates": max_node_candidates,
        "max_seconds": max_seconds,
    }

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
    leader_names: list[str] = []
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
        # Diagnostics may contain conjunction/alignment bodies that were
        # solved and removed from the ordinary DFS order.  Longitudes therefore
        # come from the authoritative full input, not the reduced DFS order.
        longitude_by_name = {
            name: longitude
            for _, name, longitude in bodies
        }
        for (depth, name), s in sorted(diagnostic_stats.items()):
            immutable_names = {
                reserved_names[i] if i < len(reserved_names) else str(i): count
                for i, count in sorted(s.get("immutable_reserved_by_obstacle", {}).items())
            }
            diagnostic_print(
                f"Planet Finder {mode}: TERMINAL BODY depth={depth}/{len(order)} body={name} "
                f"lambda={longitude_by_name[name]:.3f}deg "
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
            audits = s.get("immutable_candidate_audit", [])
            if not audits:
                continue
            by_reason = {}
            by_obstacles = {}
            for _, _, rejection, obstacle_ids in audits:
                by_reason[rejection] = by_reason.get(rejection, 0) + 1
                if obstacle_ids:
                    labels = tuple(
                        reserved_names[i] if i < len(reserved_names) else str(i)
                        for i in obstacle_ids
                    )
                    by_obstacles[labels] = by_obstacles.get(labels, 0) + 1
            diagnostic_print(
                f"Planet Finder {mode}: TERMINAL IMMUTABLE-SUMMARY "
                f"depth={depth}/{len(order)} body={name} total={len(audits):,} "
                + " ".join(
                    f"{reason}={count:,}"
                    for reason, count in sorted(by_reason.items())
                ),
                flush=True,
            )
            if by_obstacles:
                diagnostic_print(
                    f"Planet Finder {mode}: TERMINAL IMMUTABLE-OBSTACLES "
                    f"depth={depth}/{len(order)} body={name} "
                    + " ".join(
                        f"{'/'.join(labels)}={count:,}"
                        for labels, count in sorted(
                            by_obstacles.items(),
                            key=lambda item: (-item[1], item[0]),
                        )[:12]
                    ),
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

    def viable_candidates(item, depth, *, consume_body_budget=True):
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
        glyph_radii = conjunction_glyph_radii(bodies)
        anchor = xy(longitude, glyph_radii.get(name, RI - 5))
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
            if consume_body_budget and body_attempts[name] >= budget["max_node_candidates"]:
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

            run_elapsed = now - started
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
                dump_diagnostics("wall-clock")
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

            # A new leader must not cross any label already placed by DFS.
            # The opposite direction is checked earlier: a new label may not
            # cross an existing leader. Both directions are required because
            # placement order must not change collision legality.
            if any(
                segment_hits_box(path[i], path[i + 1], placed_box, 10)
                for placed_box in placed
                for i in range(len(path) - 1)
            ):
                rejected_leader += 1
                stats["leader"] += 1
                stats["leader_existing"] += 1
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
            if consume_body_budget:
                body_attempts[name] += 1
            stats["generated"] += 1
            stats["viable"] += 1
            last_yield_at = time.monotonic()
            yield box, path
            if consume_body_budget and body_attempts[name] >= budget["max_node_candidates"]:
                stats["blocked"] = "body-candidate-cap"
                diagnostic_print(
                    f"Planet Finder {mode}: BODY-CANDIDATE CAP order={order_index} "
                    f"depth={depth}/{len(order)} body={name} "
                    f"viable={body_attempts[name]:,}/{budget['max_node_candidates']:,}",
                    flush=True,
                )
                raise DepthNodeBudgetExhausted(depth, name)

    # Deterministic conjunction pre-pass. Each group is an atomic unit:
    # choose its member placements against immutable geometry and previously
    # frozen groups, but do not let siblings in the same conjunction reject
    # one another through ordinary label/leader collision rules. Glyph overlap
    # is checked explicitly from the shared radial/longitude geometry.
    by_name = {name: (i, (symbol, name, longitude)) for i, (symbol, name, longitude) in enumerate(bodies)}
    glyph_radii = conjunction_glyph_radii(bodies)
    glyph_radius = 22.0

    for group_index, group in enumerate(conjunction_groups(bodies)):
        group_items = [by_name[item[1]] for item in group]

        # The glyph layer is the hard intra-conjunction constraint. Exact
        # lambda is preserved; radial slots must keep glyph circles disjoint.
        glyph_centers = []
        for _, (_, name, longitude) in group_items:
            center = xy(longitude, glyph_radii[name])
            if any(math.hypot(center[0] - other[0], center[1] - other[1]) < 2.0 * glyph_radius
                   for other in glyph_centers):
                raise RuntimeError(
                    f"Planet Finder {mode}: conjunction glyph overlap in group {group_index + 1} at {name}"
                )
            glyph_centers.append(center)

        # Build the whole conjunction directly rather than asking the ordinary
        # recursive candidate generator to place its members independently.
        group_rows = []
        for original_index, (symbol, name, longitude) in group_items:
            gx, gy = xy(longitude, glyph_radii[name])
            w, h = label_size(mode, name)
            label_radius = max(80.0, glyph_radii[name] - 92.0)
            lx, ly = xy(longitude, label_radius)
            box = Box(lx, ly, w, h)
            leader = [(gx, gy), (lx, ly)]
            group_rows.append((original_index, symbol, name, longitude, box, leader))

        # Commit the complete conjunction at once. It now becomes fixed
        # collision geometry for every remaining recursive body.
        for original_index, symbol, name, longitude, box, leader in group_rows:
            placed.append(box)
            leaders.append(leader)
            leader_names.append(name)
            staged[original_index] = (symbol, name, longitude, box, leader)
            diagnostic_print(
                f"Planet Finder {mode}: FIXED CONJUNCTION PLACED body={name} "
                f"lambda={longitude % 360.0:.3f}deg radius={glyph_radii[name]:.1f}",
                flush=True,
            )

    # Second phase: solve the entire alignment layer recursively.  There are
    # two levels of backtracking: members within a group, and groups within the
    # alignment layer.  Nothing in this layer is truly frozen until every
    # alignment group has a mutually compatible complete placement.
    alignment_group_items = [
        [by_name[item[1]] for item in group]
        for group in alignment_groups(bodies)
    ]

    def solve_alignment_members(group_index, remaining_items):
        if not remaining_items:
            return solve_alignment_group(group_index + 1)

        # Probe a small prefix for squeaky-wheel ordering, then keep the chosen
        # body's generator alive while recursion consumes it incrementally.
        # Unlike the old batch controller, we never restart the generator or
        # replay an already-considered prefix.  Unlike full materialization, we
        # do not spend the mode clock enumerating thousands of unused choices.
        ALIGNMENT_PROBE_LIMIT = 5
        diagnostic_depth = -(group_index + 1)
        choices = []
        for item in remaining_items:
            candidate_stream = viable_candidates(
                item, diagnostic_depth, consume_body_budget=False
            )
            probe = []
            exhausted = False
            try:
                for _ in range(ALIGNMENT_PROBE_LIMIT):
                    try:
                        probe.append(next(candidate_stream))
                    except StopIteration:
                        exhausted = True
                        break
            except Exception:
                candidate_stream.close()
                raise
            choices.append((len(probe), item[1][1], item, probe, candidate_stream, exhausted))

        choices.sort(key=lambda row: (row[0], row[1]))
        count, _, item, probe, chosen_stream, exhausted = choices[0]
        for _, _, other_item, _, other_stream, _ in choices[1:]:
            other_stream.close()
        if count == 0:
            chosen_stream.close()
            return False

        original_index, (symbol, name, longitude) = item
        next_remaining = [other for other in remaining_items if other is not item]
        tried = 0
        candidate_limit = budget["max_node_candidates"]

        def try_candidate(candidate):
            box, path = candidate
            placed.append(box)
            leaders.append(path)
            leader_names.append(name)
            staged[original_index] = (symbol, name, longitude, box, path)
            solved = solve_alignment_members(group_index, next_remaining)
            if not solved:
                staged.pop(original_index, None)
                leader_names.pop()
                leaders.pop()
                placed.pop()
            return solved

        try:
            for candidate in probe:
                tried += 1
                if try_candidate(candidate):
                    return True
            if not exhausted:
                for candidate in chosen_stream:
                    tried += 1
                    if try_candidate(candidate):
                        return True
                    if tried >= candidate_limit:
                        break
        finally:
            chosen_stream.close()
        return False

    def solve_alignment_group(group_index):
        if group_index == len(alignment_group_items):
            return True
        group_items = alignment_group_items[group_index]
        placed_mark = len(placed)
        leaders_mark = len(leaders)
        names_mark = len(leader_names)
        staged_before = set(staged)

        if solve_alignment_members(group_index, list(group_items)):
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT LAYER group={group_index + 1} compatible "
                + " > ".join(item[1][1] for item in group_items),
                flush=True,
            )
            return True

        # A later group can force reconsideration of every placement made by
        # this group.  Restore exactly the geometry/staging state that existed
        # when the group was entered before its caller tries another branch.
        del placed[placed_mark:]
        del leaders[leaders_mark:]
        del leader_names[names_mark:]
        for key in list(staged):
            if key not in staged_before:
                staged.pop(key, None)
        return False

    if alignment_group_items and not solve_alignment_group(0):
        names = " | ".join(
            " > ".join(item[1][1] for item in group_items)
            for group_items in alignment_group_items
        )
        raise RuntimeError(
            f"Planet Finder {mode}: unable to solve recursive alignment layer: {names}"
        )

    if alignment_group_items:
        diagnostic_print(
            f"Planet Finder {mode}: FIXED ALIGNMENT LAYER groups={len(alignment_group_items)}",
            flush=True,
        )

    forward_stats = {"checks": 0, "pruned": 0, "witnesses": 0, "by_body": {}}
    # Bodies that actually make a forward check fail.  Without this, a prefix
    # whose every candidate is pruned before recursion leaves `deepest` at the
    # parent depth, causing the controller to blame/promote the parent instead
    # of the future body that is the real squeaky wheel.
    forward_blockers = {}
    # Forward checking is only a pruning hint.  Bound raw look-ahead work so
    # a difficult body cannot monopolize the mode clock.  Hitting this cap is
    # UNKNOWN, never proof that the branch is dead.
    forward_probe_cap = max(
        1, int(os.environ.get("PLANET_FINDER_FORWARD_PROBE_CAP", "1000"))
    )
    PROBE_LIMITED = object()

    def forward_check(next_depth):
        """Return False only when a remaining body is already provably dead.

        First require one individually viable witness for every remaining body.
        Then, when both exist, require at least one viable Child placement that
        leaves at least one compatible Grandchild placement. Look-ahead probes
        do not consume the per-body DFS candidate cap.
        """
        obstacles = [*reserved, *placed]
        immutable_count = 3
        forward_stats["checks"] += 1
        # One raw-probe budget is shared by this entire forward-check call,
        # including every individual-body witness and all child/grandchild
        # look-ahead.  Reaching the cap means UNKNOWN, never dead.
        forward_probe_used = 0

        def consume_forward_probe():
            nonlocal forward_probe_used
            if forward_probe_used >= forward_probe_cap:
                return False
            forward_probe_used += 1
            return True

        def witness_for(item, boxes, paths, obstacles_now):
            _, (_, future_name, future_longitude) = item
            w, h = label_size(mode, future_name)
            anchor = xy(future_longitude, RI - 5)
            prefix_cache = {}
            witness_raw = 0
            reasons = {"placed-overlap": 0, "existing-leader": 0, "route": 0, "leader-rim": 0, "leader-graze": 0}
            for _, _, future_box in legal_candidate_positions(
                future_longitude, w, h, reserved, displacement_scale
            ):
                if not consume_forward_probe():
                    return PROBE_LIMITED, None, witness_raw, reasons
                witness_raw += 1
                if any(boxes_overlap(future_box, other, 14) for other in boxes):
                    reasons["placed-overlap"] += 1
                    continue
                if any(
                    segment_hits_box(seg[i], seg[i + 1], future_box, 10)
                    for seg in paths
                    for i in range(len(seg) - 1)
                ):
                    reasons["existing-leader"] += 1
                    continue
                center = (future_box.x, future_box.y)
                path = route(
                    anchor,
                    center,
                    obstacles_now,
                    allow_initial_escape_count=immutable_count,
                    prefix_cache=prefix_cache,
                )
                if path is None:
                    reasons["route"] += 1
                    continue
                if leader_hits_zodiac_rim(path):
                    reasons["leader-rim"] += 1
                    continue
                if leaders_too_close(path, paths):
                    reasons["leader-graze"] += 1
                    if len(paths) == 1 and future_name in {"Moon", "Mercury"}:
                        min_dist, pair = minimum_leader_separation(path, paths)
                        if pair is not None:
                            diagnostic_print(
                                f"Planet Finder {mode}: LEADER-GRAZE "
                                f"proposed={future_name} existing={leader_names[pair[0]]} "
                                f"distance={min_dist:.3f} clearance={LEADER_TO_LEADER_CLEARANCE:.3f} "
                                f"candidate=({future_box.x:.1f},{future_box.y:.1f}) "
                                f"segments={pair[1]}/{pair[2]}",
                                level=3,
                                flush=True,
                            )
                    continue
                return future_box, path, witness_raw, reasons
            return None, None, witness_raw, reasons

        # Existing individual feasibility test for every future body.
        for future_depth in range(next_depth, len(order)):
            item = order[future_depth]
            _, (_, future_name, _) = item
            future_box, future_path, witness_raw, witness_reasons = witness_for(
                item, placed, leaders, obstacles
            )
            if future_box is PROBE_LIMITED:
                diagnostic_print(
                    f"Planet Finder {mode}: FORWARD PROBE CAP body={future_name} "
                    f"raw={witness_raw:,}/{forward_probe_cap:,}; treating as unknown",
                    level=2,
                    flush=True,
                )
                continue
            witness = future_box is not None
            body_stat = forward_stats["by_body"].setdefault(
                future_name, {"checks": 0, "witnesses": 0, "dead": 0, "raw": 0,
                               "reasons": {"placed-overlap": 0, "existing-leader": 0,
                                          "route": 0, "leader-rim": 0, "leader-graze": 0}}
            )
            body_stat["checks"] += 1
            body_stat["raw"] += witness_raw
            for reason, count in witness_reasons.items():
                body_stat["reasons"][reason] += count
            if witness:
                body_stat["witnesses"] += 1
                forward_stats["witnesses"] += 1
            else:
                body_stat["dead"] += 1
                forward_stats["pruned"] += 1
                forward_blockers[future_name] = forward_blockers.get(future_name, 0) + 1
                if next_depth == 1 and order[0][1][1] == "Sun":
                    diagnostic_print(
                        f"Planet Finder {mode}: SUN-PREFIX DEAD-GATE "
                        f"sun-check={forward_stats['checks']:,} "
                        f"future-body={future_name} raw={witness_raw:,} "
                        f"prefix-obstacles={len(obstacles):,}",
                        level=3,
                        flush=True,
                    )
                return False

        # Child -> Grandchild look-ahead intentionally disabled.
        # Individual future-body witness checks remain active above.
        # Ordinary DFS now owns all multi-body compatibility decisions.

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

        run_elapsed = now - started
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
            leader_names.append(name)
            staged[original_index] = (symbol, name, longitude, box, path)

            child_deepest_before = deepest
            child_nodes_before = nodes
            child_backtracks_before = backtracks
            try:
                # Forward checking asks only for one viable witness for every
                # remaining body. Zero proves this prefix is dead; one is
                # enough to preserve it for the real DFS.

                if search(depth + 1):
                    return True
            finally:
                staged.pop(original_index, None)
                leaders.pop()
                leader_names.pop()
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
        # Prefer the body that actually caused forward-check pruning.  A
        # forward-pruned child is never entered by DFS, so `deepest` otherwise
        # misidentifies the parent as the blocker and the controller repeatedly
        # promotes the wrong body.
        if forward_blockers:
            order_rank = {item[1][1]: depth for depth, item in enumerate(order)}
            blocker = min(
                forward_blockers,
                key=lambda name: (-forward_blockers[name], order_rank.get(name, len(order))),
            )
            diagnostic_print(
                f"Planet Finder {mode}: FORWARD BLOCKER body={blocker} "
                f"prunes={forward_blockers[blocker]:,} all={forward_blockers}",
                flush=True,
            )
        else:
            # No forward-pruning evidence: fall back to the deepest DFS body.
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
    if exhausted and forward_stats["by_body"]:
        diagnostic_print(
            f"Planet Finder {mode}: FORWARD REJECTION BREAKDOWN",
            flush=True,
        )
        for body, stat in sorted(forward_stats["by_body"].items()):
            reasons = stat.get("reasons", {})
            diagnostic_print(
                f"Planet Finder {mode}: FORWARD BODY body={body} "
                f"checks={stat['checks']:,} dead={stat['dead']:,} raw={stat['raw']:,} "
                f"placed-overlap={reasons.get('placed-overlap', 0):,} "
                f"existing-leader={reasons.get('existing-leader', 0):,} "
                f"route={reasons.get('route', 0):,} "
                f"leader-rim={reasons.get('leader-rim', 0):,} "
                f"leader-graze={reasons.get('leader-graze', 0):,}",
                flush=True,
            )

    return SearchOutcome(
        "SOLVED" if len(solutions) >= target_solutions else "EXHAUSTED",
        solutions,
        contest_keys,
        blocker,
        blocker_stats,
    )