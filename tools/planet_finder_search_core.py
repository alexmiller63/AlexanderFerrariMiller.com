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
    legal_candidate_positions, route, alignment_groups, conjunction_groups,
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


def _search_alignment_fallback(preplacement, groups, placed, leaders, leader_names,
                               staged, search, solve_alignment_group):
    """Try a planned layer, then restore it before recursive backtracking."""
    if preplacement:
        capped_preplacement = None
        try:
            if search(0):
                return True
        except DepthNodeBudgetExhausted as exc:
            # A cap reached under the planner's first complete alignment is
            # evidence that this preplacement is a dead/expensive branch, not
            # proof that the alignment layer itself is exhausted. Restore it
            # and let recursive alignment backtracking try sibling placements.
            capped_preplacement = exc
        planned, _ = preplacement
        for group in groups:
            for original_index, _ in group:
                staged.pop(original_index)
        del placed[-len(planned):]
        del leaders[-len(planned):]
        del leader_names[-len(planned):]
        diagnostic_print(
            "Planet Finder: ALIGNMENT PREPLACEMENT "
            + (
                f"CAPPED body={capped_preplacement.name}; "
                if capped_preplacement is not None else "BLOCKED; "
            )
            + "retrying recursive alignment layer",
            flush=True,
        )
    if groups:
        return solve_alignment_group(0)
    return search(0)


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
    # Diagnostic only: distinguish genuinely different admitted geometries
    # from repeated/equivalent viable candidates.  This never filters or
    # reorders candidates and therefore cannot change search behavior.
    viable_geometry_seen = {}
    # Diagnostic only: record what happens to Venus under individually viable
    # parent placements. The Uranus form exposes the exact W36
    # Pluto > Uranus > Venus terminal chain without altering search behavior.
    pluto_venus_prefixes = []
    uranus_venus_prefixes = []
    # Diagnostic only: summarize how Mercury's admitted candidates traverse
    # label-position space.  This does not filter, reorder, or score anything.
    mercury_candidate_stream = []
    # Diagnostic only: recursive alignment Mercury placement -> Venus work.
    # Never consulted by candidate generation or search decisions.
    alignment_mercury_trials = []
    solutions = []
    solution_keys = set()
    contest_keys = []
    current_body = "-"
    exhausted = False
    terminal_validation_checks = 0
    terminal_validation_rejections = 0
    terminal_validation_errors = {}
    terminal_validation_sun_leaders = {}

    def dump_diagnostics(reason):
        # A capped ordering is expected control flow, not a terminal failure.
        # Emit one compact summary for it; full forensic dumps are reserved
        # for genuinely terminal/exhausted searches. This keeps legitimate
        # ordering exploration from exhausting the GitHub Actions log.
        if reason.startswith("body-attempt-cap"):
            order_names = " > ".join(item[1][1] for item in order)
            capped_stats = [
                (depth, name, stats)
                for (depth, name), stats in diagnostic_stats.items()
                if stats.get("blocked") == "body-candidate-cap"
            ]
            rejection_summary = ""
            if capped_stats:
                depth, name, stats = capped_stats[-1]
                rejection_summary = (
                    f" capped_body={name} depth={depth}/{len(order)} "
                    f"generated={stats.get('generated', 0):,} viable={stats.get('viable', 0):,} "
                    f"rejects[immutable-reserved={stats.get('immutable_reserved', 0):,},"
                    f"immutable-rim={stats.get('immutable_rim', 0):,},"
                    f"placed-overlap={stats.get('overlap', 0):,},"
                    f"existing-leader={stats.get('leader_existing', 0):,},"
                    f"route={stats.get('route', 0):,},"
                    f"leader-rim={stats.get('leader_rim', 0):,},"
                    f"leader-graze={stats.get('leader_graze', 0):,}]"
                )
                # Diagnostic only: when a parent body consumes its viable
                # candidate allowance because every descendant subtree fails,
                # show aggregate behavior at every deeper depth.  This extends
                # the visibility from the immediate child through the full
                # descendant chain without changing search, accounting,
                # ordering, geometry, or budgets.
                for descendant_depth in range(depth + 1, len(order)):
                    descendant_name = order[descendant_depth][1][1]
                    descendant_stats = diagnostic_stats.get(
                        (descendant_depth, descendant_name), {}
                    )
                    rejection_summary += (
                        f" descendant[{descendant_name} "
                        f"depth={descendant_depth}/{len(order)} "
                        f"visits={depth_visits.get(descendant_depth, 0):,} "
                        f"dead_ends={dead_end_visits.get((descendant_depth, descendant_name), 0):,} "
                        f"generated={descendant_stats.get('generated', 0):,} "
                        f"viable={descendant_stats.get('viable', 0):,} "
                        f"rejects[immutable-reserved={descendant_stats.get('immutable_reserved', 0):,},"
                        f"immutable-rim={descendant_stats.get('immutable_rim', 0):,},"
                        f"placed-overlap={descendant_stats.get('overlap', 0):,},"
                        f"existing-leader={descendant_stats.get('leader_existing', 0):,},"
                        f"route={descendant_stats.get('route', 0):,},"
                        f"leader-rim={descendant_stats.get('leader_rim', 0):,},"
                        f"leader-graze={descendant_stats.get('leader_graze', 0):,}]]"
                    )
            validation_summary = ""
            if terminal_validation_checks:
                ranked_validation = sorted(
                    terminal_validation_errors.items(),
                    key=lambda item: (-item[1], item[0]),
                )
                validation_summary = (
                    f" terminal_validation[checks={terminal_validation_checks:,},"
                    f"rejected={terminal_validation_rejections:,},"
                    + ",".join(f"{error}={count:,}" for error, count in ranked_validation)
                    + "]"
                )
                if terminal_validation_sun_leaders:
                    ranked_sun_leaders = sorted(
                        terminal_validation_sun_leaders.items(),
                        key=lambda item: (-item[1], item[0]),
                    )
                    validation_summary += (
                        " sun_label_hit_by["
                        + ",".join(
                            f"{name}={count:,}" for name, count in ranked_sun_leaders
                        )
                        + "]"
                    )
            diagnostic_print(
                f"Planet Finder {mode}: CAPPED SUMMARY order={order_index} "
                f"nodes={nodes:,} deepest={deepest}/{len(order)} "
                f"current_body={current_body} sequence={order_names}"
                f"{rejection_summary}{validation_summary}",
                flush=True,
            )
            if pluto_venus_prefixes:
                keys = ("generated", "viable", "immutable_reserved", "immutable_rim",
                        "overlap", "leader_existing", "route", "leader_rim", "leader_graze")
                totals = {key: sum(row[key] for row in pluto_venus_prefixes) for key in keys}
                zero_viable = sum(1 for row in pluto_venus_prefixes if row["viable"] == 0)
                diagnostic_print(
                    f"Planet Finder {mode}: PLUTO-VENUS PREFIX SUMMARY "
                    f"parents={len(pluto_venus_prefixes):,} zero-viable={zero_viable:,} "
                    f"venus-generated={totals['generated']:,} venus-viable={totals['viable']:,} "
                    f"rejects[immutable-reserved={totals['immutable_reserved']:,},"
                    f"immutable-rim={totals['immutable_rim']:,},"
                    f"placed-overlap={totals['overlap']:,},"
                    f"existing-leader={totals['leader_existing']:,},"
                    f"route={totals['route']:,},leader-rim={totals['leader_rim']:,},"
                    f"leader-graze={totals['leader_graze']:,}]",
                    flush=True,
                )
            if alignment_mercury_trials:
                distinct = {}
                for row in alignment_mercury_trials:
                    sig = row["signature"]
                    aggregate = distinct.setdefault(sig, {
                        "box": row["box"], "visits": 0,
                        "venus_generated": 0, "venus_viable": 0,
                    })
                    aggregate["visits"] += 1
                    aggregate["venus_generated"] += row["venus_generated"]
                    aggregate["venus_viable"] += row["venus_viable"]
                ranked = sorted(
                    distinct.values(),
                    key=lambda row: (-row["venus_viable"], -row["venus_generated"], row["box"]),
                )
                samples = "; ".join(
                    f"box={row['box']} visits={row['visits']} "
                    f"V[gen={row['venus_generated']},ok={row['venus_viable']}]"
                    for row in ranked[:20]
                )
                mercury_summary = (
                    f"Planet Finder {mode}: ALIGNMENT MERCURY->VENUS SUMMARY "
                    f"trials={len(alignment_mercury_trials):,} distinct={len(distinct):,} "
                    f"venus-positive={sum(1 for row in distinct.values() if row['venus_viable'] > 0):,} "
                    f"samples={samples}"
                )
                diagnostic_print(mercury_summary, flush=True)
                summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
                if summary_path:
                    with open(summary_path, "a", encoding="utf-8") as summary_file:
                        summary_file.write("### Mercury alignment → Venus viability diagnostic\n\n" + mercury_summary + "\n\n")
            if uranus_venus_prefixes:
                keys = ("generated", "viable", "immutable_reserved", "immutable_rim",
                        "overlap", "leader_existing", "route", "leader_rim", "leader_graze")
                totals = {key: sum(row[key] for row in uranus_venus_prefixes) for key in keys}
                zero_viable = sum(1 for row in uranus_venus_prefixes if row["viable"] == 0)
                worst = sorted(
                    uranus_venus_prefixes,
                    key=lambda row: (row["viable"], -sum(row[key] for key in keys[2:])),
                )[:5]
                samples = "; ".join(
                    f"box={row['uranus_box']} path={row['uranus_path']} "
                    f"V[gen={row['generated']},ok={row['viable']},res={row['immutable_reserved']},"
                    f"rim={row['immutable_rim']},ov={row['overlap']},lead={row['leader_existing']},"
                    f"route={row['route']},lrim={row['leader_rim']},graze={row['leader_graze']}]"
                    for row in worst
                )
                summary = (
                    f"Planet Finder {mode}: W36 URANUS-VENUS DEAD-END SUMMARY "
                    f"prefixes={len(uranus_venus_prefixes):,} zero-viable={zero_viable:,} "
                    f"venus-generated={totals['generated']:,} venus-viable={totals['viable']:,} "
                    f"rejects[immutable-reserved={totals['immutable_reserved']:,},"
                    f"immutable-rim={totals['immutable_rim']:,},placed-overlap={totals['overlap']:,},"
                    f"existing-leader={totals['leader_existing']:,},route={totals['route']:,},"
                    f"leader-rim={totals['leader_rim']:,},leader-graze={totals['leader_graze']:,}] "
                    f"samples={samples}"
                )
                diagnostic_print(summary, flush=True)
                summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
                if summary_path:
                    with open(summary_path, "a", encoding="utf-8") as summary_file:
                        summary_file.write("### W36 Uranus → Venus dead-end diagnostic\n\n" + summary + "\n\n")
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

        # Diagnostic-only W36 attribution: identify which already-placed
        # alignment labels/leaders most often prevent Venus from becoming a
        # viable ordinary-body placement.  These counters are observational
        # only and never participate in search decisions.
        venus_attribution = {
            "overlap": {},
            "existing-leader": {},
            "leader-graze": {},
        }
        venus_own_graze = 0
        for (diag_depth, diag_name), stats in diagnostic_stats.items():
            if diag_name != "Venus":
                continue
            venus_own_graze += stats.get("own_label_graze", 0)
            for label, count in stats.get("overlap_by_label", {}).items():
                venus_attribution["overlap"][label] = venus_attribution["overlap"].get(label, 0) + count
            for label, count in stats.get("existing_leader_by_name", {}).items():
                venus_attribution["existing-leader"][label] = venus_attribution["existing-leader"].get(label, 0) + count
            for label, count in stats.get("leader_graze_by_name", {}).items():
                venus_attribution["leader-graze"][label] = venus_attribution["leader-graze"].get(label, 0) + count
        for kind, counts in venus_attribution.items():
            top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:12]
            diagnostic_print(
                f"Planet Finder {mode}: VENUS BLOCKERS kind={kind} "
                + (" ".join(f"{name}={count:,}" for name, count in top) if top else "none"),
                flush=True,
            )
        diagnostic_print(
            f"Planet Finder {mode}: VENUS BLOCKERS kind=own-label-graze count={venus_own_graze:,}",
            flush=True,
        )
        diagnostic_print(
            f"Planet Finder {mode}: TERMINAL BEST-PARTIAL deepest={deepest}/{len(order)}",
            flush=True,
        )

    def cap_lineage(depth):
        """Diagnostic-only viable counts for grandparent -> parent -> current."""
        parts = []
        for lineage_depth, role in (
            (depth - 2, "grandparent"),
            (depth - 1, "parent"),
            (depth, "current"),
        ):
            if 0 <= lineage_depth < len(order):
                lineage_name = order[lineage_depth][1][1]
                parts.append(
                    f"{role}[{lineage_name} depth={lineage_depth} "
                    f"viable={body_attempts.get(lineage_name, 0):,}]"
                )
        return " ".join(parts)

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
            # Diagnostic-only attribution for the W36 Venus dead end.
            # These maps never affect candidate legality or ordering.
            "overlap_by_label": {},
            "existing_leader_by_name": {},
            "leader_graze_by_name": {},
            "own_label_graze": 0,
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
            if consume_body_budget and body_attempts[name] >= budget["max_node_candidates"]:
                stats["blocked"] = "body-candidate-cap"
                diagnostic_print(
                    f"Planet Finder {mode}: BODY-CANDIDATE CAP order={order_index} "
                    f"depth={depth}/{len(order)} body={name} "
                    f"viable={body_attempts[name]:,}/{budget['max_node_candidates']:,} "
                    f"unique_geometry={len(viable_geometry_seen.get(name, ())):,} "
                    f"duplicates={max(0, body_attempts[name] - len(viable_geometry_seen.get(name, ()))):,} "
                    f"lineage={cap_lineage(depth)}",
                    flush=True,
                )
                if name == "Mercury" and mercury_candidate_stream:
                    # Use cumulative doubling bands so the output lines map
                    # directly onto the W1 200/400/800/1600/3200 ladder.
                    bounds = (200, 400, 800, 1600, 3200)
                    start = 0
                    for stop in bounds:
                        if start >= len(mercury_candidate_stream):
                            break
                        band = mercury_candidate_stream[start:min(stop, len(mercury_candidate_stream))]
                        radii = [row[0] for row in band]
                        angles = [row[1] for row in band]
                        xs = [row[2] for row in band]
                        ys = [row[3] for row in band]
                        sectors = [0] * 8
                        for angle in angles:
                            sectors[min(7, int(angle // 45.0))] += 1
                        diagnostic_print(
                            f"Planet Finder {mode}: MERCURY-CANDIDATE-BAND "
                            f"range={start + 1}-{start + len(band)} "
                            f"radius[min={min(radii):.1f},max={max(radii):.1f},mean={sum(radii)/len(radii):.1f}] "
                            f"x[min={min(xs):.1f},max={max(xs):.1f}] "
                            f"y[min={min(ys):.1f},max={max(ys):.1f}] "
                            f"sectors45={','.join(str(value) for value in sectors)}",
                            flush=True,
                        )
                        start = stop
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
            overlap_indices = [i for i, b in enumerate(placed) if boxes_overlap(box, b, 14)]
            overlaps_placed = bool(overlap_indices)
            timing["overlap"] += time.monotonic() - t0
            if overlaps_placed:
                rejected_overlap += 1
                stats["overlap"] += 1
                if name == "Venus":
                    for i in overlap_indices:
                        blocker = leader_names[i] if i < len(leader_names) else f"placed_{i}"
                        stats["overlap_by_label"][blocker] = stats["overlap_by_label"].get(blocker, 0) + 1
                continue
            t0 = time.monotonic()
            existing_leader_hits = [
                leader_index
                for leader_index, seg in enumerate(leaders)
                if any(segment_hits_box(seg[i], seg[i + 1], box, 10)
                       for i in range(len(seg) - 1))
            ]
            hit_existing_leader = bool(existing_leader_hits)
            timing["existing_leader"] += time.monotonic() - t0
            if hit_existing_leader:
                rejected_leader += 1
                stats["leader"] += 1
                stats["leader_existing"] += 1
                if name == "Venus":
                    for leader_index in existing_leader_hits:
                        blocker = leader_names[leader_index] if leader_index < len(leader_names) else f"leader_{leader_index}"
                        stats["existing_leader_by_name"][blocker] = stats["existing_leader_by_name"].get(blocker, 0) + 1
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
                target_box=box,
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

            # route() now returns the exact drawable path, including the
            # final 2 px label-boundary clearance.  Validate that path directly;
            # do not calculate a second presentation geometry here.
            rendered_path = path

            # A routed leader must make monotonic progress toward its rendered
            # label endpoint.  Reject overshoot/backtracking doglegs where an
            # intermediate waypoint gets closer to the endpoint and a later
            # waypoint moves away again.  W01 Mixed Saturn measured as
            # (306.0,672.4) -> (350.0,516.8) -> label edge near (362.1,523.1):
            # the route overshoots above the label and reverses on approach.
            endpoint = rendered_path[-1]
            distances = [
                math.hypot(point[0] - endpoint[0], point[1] - endpoint[1])
                for point in rendered_path
            ]
            route_backtracks = any(
                distances[i + 1] > distances[i] + 1e-6
                for i in range(len(distances) - 1)
            )

            own_label_bad = route_backtracks or any(
                segment_hits_box(rendered_path[i], rendered_path[i + 1], box, 0.5)
                for i in range(max(0, len(rendered_path) - 2))
            )
            # The final rendered segment is allowed to terminate on the true
            # boundary, but it must not penetrate the label interior before
            # that endpoint.  A slightly shrunken box makes that distinction
            # explicit instead of exempting the whole final segment.
            if len(rendered_path) >= 2 and segment_hits_box(
                rendered_path[-2], rendered_path[-1], box, -0.5
            ):
                own_label_bad = True

            if own_label_bad:
                rejected_leader += 1
                stats["leader"] += 1
                stats["leader_graze"] += 1
                if name == "Venus":
                    stats["own_label_graze"] += 1
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
                if name == "Venus":
                    _, closest_pair = minimum_leader_separation(path, leaders)
                    if closest_pair is not None:
                        leader_index = closest_pair[0]
                        blocker = leader_names[leader_index] if leader_index < len(leader_names) else f"leader_{leader_index}"
                        stats["leader_graze_by_name"][blocker] = stats["leader_graze_by_name"].get(blocker, 0) + 1
                continue
            # Diagnostic-only geometry signature.  Round below rendering
            # precision so numerically insignificant float noise does not make
            # equivalent candidates appear distinct.  Include the routed leader
            # because the same label box with a different route is a materially
            # different search choice.
            geometry_signature = (
                round(box.x, 6), round(box.y, 6),
                round(box.w, 6), round(box.h, 6),
                tuple((round(px, 6), round(py, 6)) for px, py in path),
            )
            seen = viable_geometry_seen.setdefault(name, set())
            seen.add(geometry_signature)

            if name == "Mercury" and consume_body_budget:
                # Polar coordinates around the exact Mercury anchor expose
                # whether enumeration explores broadly or marches through one
                # sector/radius before reaching the rest of the lattice.
                dx = box.x - anchor[0]
                dy = box.y - anchor[1]
                mercury_candidate_stream.append((
                    math.hypot(dx, dy),
                    math.degrees(math.atan2(dy, dx)) % 360.0,
                    box.x,
                    box.y,
                ))

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
                    f"viable={body_attempts[name]:,}/{budget['max_node_candidates']:,} "
                    f"unique_geometry={len(viable_geometry_seen.get(name, ())):,} "
                    f"duplicates={max(0, body_attempts[name] - len(viable_geometry_seen.get(name, ()))):,} "
                    f"lineage={cap_lineage(depth)}",
                    flush=True,
                )
                if name == "Mercury" and mercury_candidate_stream:
                    # Use cumulative doubling bands so the output lines map
                    # directly onto the W1 200/400/800/1600/3200 ladder.
                    bounds = (200, 400, 800, 1600, 3200)
                    start = 0
                    for stop in bounds:
                        if start >= len(mercury_candidate_stream):
                            break
                        band = mercury_candidate_stream[start:min(stop, len(mercury_candidate_stream))]
                        radii = [row[0] for row in band]
                        angles = [row[1] for row in band]
                        xs = [row[2] for row in band]
                        ys = [row[3] for row in band]
                        sectors = [0] * 8
                        for angle in angles:
                            sectors[min(7, int(angle // 45.0))] += 1
                        diagnostic_print(
                            f"Planet Finder {mode}: MERCURY-CANDIDATE-BAND "
                            f"range={start + 1}-{start + len(band)} "
                            f"radius[min={min(radii):.1f},max={max(radii):.1f},mean={sum(radii)/len(radii):.1f}] "
                            f"x[min={min(xs):.1f},max={max(xs):.1f}] "
                            f"y[min={min(ys):.1f},max={max(ys):.1f}] "
                            f"sectors45={','.join(str(value) for value in sectors)}",
                            flush=True,
                        )
                        start = stop
                raise DepthNodeBudgetExhausted(depth, name)

    # Deterministic conjunction pre-pass.  Anchors are geometric attachment
    # points only: exact lambda at the common RI-5 radius.  The visible glyph is
    # in the displaced label, so no invisible anchor-glyph staggering or glyph
    # collision calculation belongs in the search model.
    by_name = {name: (i, (symbol, name, longitude)) for i, (symbol, name, longitude) in enumerate(bodies)}

    conjunction_group_list = conjunction_groups(bodies)
    conjunction_names = {
        item[1]
        for group in conjunction_group_list
        for item in group
    }

    # Placement geometry is independent of conjunction status.  Build the
    # coordinated alignment layer from a view in which conjunction members are
    # restored to the ordinary alignment population.  Conjunction metadata is
    # retained separately and is used only to make those members atomic when
    # backtracking.
    alignment_source = list(bodies)
    alignment_group_items = [
        [by_name[item[1]] for item in group]
        for group in alignment_groups(alignment_source)
    ]

    def plan_alignment_layer(groups=None):
        """Preplace groups as one ordered, route-compatible layer.

        This is the shared coordinated-placement algorithm for both ordinary
        close alignments and conjunction blobs. Crossing the conjunction
        threshold changes atomicity only; it does not change placement geometry.
        """
        groups = alignment_group_items if groups is None else groups
        items = [item for group in groups for item in group]
        if not items:
            return None
        # Ordinary recursive placement already handles broader alignments.
        # Reserve the group planner for the close pairs that make sequential
        # first-fit placement expensive in the wider text modes.
        close_gap = min(
            (right[1][2] - left[1][2]) % 360.0
            for group in groups
            for left, right in zip(group, group[1:])
        )
        if close_gap >= 3.0:
            return None
        pools = {}
        order_names = [item[1][1] for item in items]
        longitudes = {item[1][1]: item[1][2] for item in items}
        anchors = {name: xy(longitude, RI - 5)
                   for name, longitude in longitudes.items()}
        group_names = [[item[1][1] for item in group] for group in groups]
        alignment_path_rejects = {"route": 0, "label_hit": 0, "rim_hit": 0, "leader_graze": 0}
        alignment_samples = {}

        def label_angle(row, reference):
            x, y, _ = row
            angle = (math.degrees(math.atan2(CY - y, x - CX)) - 180.0) % 360.0
            return (angle - reference) % 360.0

        def ordered(chosen):
            for names in group_names:
                reference = longitudes[names[0]] - 90.0
                present = [name for name in names if name in chosen]
                if any(label_angle(chosen[a], reference) >= label_angle(chosen[b], reference)
                       for a, b in zip(present, present[1:])):
                    return False
            return True

        def planned_paths(chosen):
            paths = {}
            for name in order_names:
                if name not in chosen:
                    continue
                x, y, _ = chosen[name]
                other_boxes = [row[2] for other, row in chosen.items() if other != name]
                path = route(
                    anchors[name], (x, y), reserved + placed + other_boxes,
                    allow_initial_escape_count=3,
                    target_box=chosen[name][2],
                )
                label_hit = path is not None and any(
                    segment_hits_box(path[i], path[i + 1], box, PLACED_LABEL_LEADER_CLEARANCE)
                    for box in other_boxes for i in range(len(path) - 1)
                )
                rim_hit = path is not None and leader_hits_zodiac_rim(path)
                prior_paths = leaders + list(paths.values())
                graze = path is not None and leaders_too_close(path, prior_paths)
                if path is None or label_hit or rim_hit or graze:
                    if path is None:
                        alignment_path_rejects["route"] += 1
                        sample_key = "route"
                    elif label_hit:
                        alignment_path_rejects["label_hit"] += 1
                        sample_key = "label_hit"
                    elif rim_hit:
                        alignment_path_rejects["rim_hit"] += 1
                        sample_key = "rim_hit"
                    else:
                        alignment_path_rejects["leader_graze"] += 1
                        sample_key = "leader_graze"
                    if sample_key not in alignment_samples:
                        alignment_samples[sample_key] = (
                            f"body={name} chosen={','.join(chosen.keys())} "
                            f"path={None if path is None else [(round(px,1), round(py,1)) for px,py in path]}"
                        )
                    return None
                paths[name] = path
            return paths

        for _, (_, name, longitude) in items:
            w, h = label_size(mode, name)
            natural = xy(longitude, PREFERRED_LABEL_RADII[0])
            immutable_diag = {} if name == "Sun" and abs(longitude - 101.0) < 1e-9 else None
            options = [
                row for row in legal_candidate_positions(
                    longitude, w, h, reserved, displacement_scale, immutable_diag
                )
                if not any(boxes_overlap(row[2], box, LABEL_COLLISION_PADDING) for box in placed)
                and not any(segment_hits_box(path[i], path[i + 1], row[2], 10)
                            for path in leaders for i in range(len(path) - 1))
            ]
            if immutable_diag is not None:
                trace = immutable_diag.get("sun_1deg_first_candidate_trace")
                diagnostic_print(
                    f"Planet Finder {mode}: SUN 1DEG FIRST-CANONICAL {trace}",
                    flush=True,
                )
                audit = immutable_diag.get("immutable_candidate_audit", [])
                natural_trace = xy(longitude, PREFERRED_LABEL_RADII[0])
                rejected = sorted(
                    audit,
                    key=lambda row: math.hypot(row[0] - natural_trace[0], row[1] - natural_trace[1]),
                    reverse=True,
                )[:12]
                diagnostic_print(
                    f"Planet Finder {mode}: SUN 1DEG WIDEST-IMMUTABLE-REJECTS " + ";".join(
                        f"x={x:.3f},y={y:.3f},d={math.hypot(x-natural_trace[0], y-natural_trace[1]):.3f},reason={reason},hits={hits}"
                        for x, y, reason, hits in rejected
                    ),
                    flush=True,
                )
            # Wide-first is a planner invariant, not conjunction-specific
            # behavior.  Keep the widest legal alternatives in the bounded
            # pool and try them before progressively narrower placements.
            options.sort(
                key=lambda row: math.hypot(row[0] - natural[0], row[1] - natural[1]),
                reverse=True,
            )
            pools[name] = options[:80]
            if not pools[name]:
                return None

        nodes = 0
        assign_visits = {}
        assign_rejects = {"empty_future": 0, "circular_order": 0, "planned_path": 0}
        deepest_alignment_choice = 0
        termination_reason = "exhausted"

        def assign(remaining, available, chosen):
            nonlocal nodes, deepest_alignment_choice, termination_reason
            depth_here = len(chosen)
            deepest_alignment_choice = max(deepest_alignment_choice, depth_here)
            assign_visits[depth_here] = assign_visits.get(depth_here, 0) + 1
            if not remaining:
                return (chosen, planned_paths(chosen))
            name = min(remaining, key=lambda candidate: (len(available[candidate]), order_names.index(candidate)))
            others = [candidate for candidate in remaining if candidate != name]
            for row in available[name]:
                nodes += 1
                if nodes > 50000 or (refinement_deadline is not None and
                                     time.monotonic() >= refinement_deadline):
                    termination_reason = "node-limit" if nodes > 50000 else "deadline"
                    if "termination" not in alignment_samples:
                        alignment_samples["termination"] = (
                            f"depth={depth_here}/{len(order_names)} next={name} "
                            f"chosen={','.join(chosen.keys()) or '-'}"
                        )
                    return None
                next_available = {
                    candidate: [option for option in available[candidate]
                                if not boxes_overlap(row[2], option[2], LABEL_COLLISION_PADDING)]
                    for candidate in others
                }
                if any(not next_available[candidate] for candidate in others):
                    assign_rejects["empty_future"] += 1
                    continue
                trial = {**chosen, name: row}
                if not ordered(trial):
                    assign_rejects["circular_order"] += 1
                    if "circular_order" not in alignment_samples:
                        alignment_samples["circular_order"] = (
                            f"chosen={','.join(trial.keys())} "
                            + " angles=" + ",".join(
                                f"{member}:{label_angle(trial[member], longitudes[group_names[0][0]] - 90.0):.3f}"
                                for member in group_names[0] if member in trial
                            )
                        )
                    continue
                if planned_paths(trial) is None:
                    assign_rejects["planned_path"] += 1
                    continue
                result = assign(others, next_available, trial)
                if result is not None:
                    return result
            return None

        result = assign(order_names, pools, {})
        planned = result[0] if result else {}
        if result is not None:
            termination_reason = "success"
        summary_lines = [
            f"### Planet Finder alignment diagnostic — {mode}",
            "",
            f"- Members: {', '.join(order_names)}",
            f"- Result: {termination_reason}",
            f"- Nodes: {nodes:,}",
            f"- Deepest: {deepest_alignment_choice}/{len(order_names)}",
            f"- Complete alignment constructed: {'yes' if result is not None else 'no'}",
            f"- Visits by depth: {assign_visits}",
            f"- Empty-future prunes: {assign_rejects['empty_future']:,}",
            f"- Circular-order rejects: {assign_rejects['circular_order']:,}",
            f"- Planned-path rejects: {assign_rejects['planned_path']:,}",
            f"- Path causes: route={alignment_path_rejects['route']:,}, "
            f"label_hit={alignment_path_rejects['label_hit']:,}, "
            f"rim_hit={alignment_path_rejects['rim_hit']:,}, "
            f"leader_graze={alignment_path_rejects['leader_graze']:,}",
        ]
        if alignment_samples:
            summary_lines += ["", "Representative first failures:"]
            summary_lines += [f"- {key}: {value}" for key, value in alignment_samples.items()]
        summary = "\n".join(summary_lines)
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as summary_file:
                summary_file.write(summary + "\n\n")
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT SUMMARY result={termination_reason} "
            f"nodes={nodes:,} deepest={deepest_alignment_choice}/{len(order_names)} "
            f"rejects[empty={assign_rejects['empty_future']:,},order={assign_rejects['circular_order']:,},"
            f"path={assign_rejects['planned_path']:,}] "
            f"path-causes[route={alignment_path_rejects['route']:,},label={alignment_path_rejects['label_hit']:,},"
            f"rim={alignment_path_rejects['rim_hit']:,},graze={alignment_path_rejects['leader_graze']:,}]",
            flush=True,
        )
        return result

    def stage_alignment_preplacement(alignment_preplacement):
        if not alignment_preplacement:
            return
        planned, paths = alignment_preplacement
        for group in alignment_group_items:
            for original_index, (symbol, name, longitude) in group:
                box = planned[name][2]
                path = paths[name]
                placed.append(box)
                leaders.append(path)
                leader_names.append(name)
                staged[original_index] = (symbol, name, longitude, box, path)

    def solve_alignment_members(group_index, remaining_items):
        if not remaining_items:
            return solve_alignment_group(group_index + 1)

        # Place members in the circular lambda order supplied by
        # alignment_groups().  Keep one stream alive while recursion consumes
        # its candidates, so backtracking never replays a prefix.
        diagnostic_depth = -(group_index + 1)
        item = remaining_items[0]
        original_index, (symbol, name, longitude) = item
        next_remaining = remaining_items[1:]
        tried = 0
        candidate_limit = budget["max_node_candidates"]

        def try_candidate(candidate):
            box, path = candidate
            placed.append(box)
            leaders.append(path)
            leader_names.append(name)
            staged[original_index] = (symbol, name, longitude, box, path)
            mercury_before = None
            mercury_signature = None
            if name == "Mercury":
                mercury_signature = (
                    round(box.x, 3), round(box.y, 3), round(box.w, 3), round(box.h, 3),
                    tuple((round(px, 3), round(py, 3)) for px, py in path),
                )
                mercury_before = {
                    key: sum(
                        stats.get(key, 0)
                        for (diag_depth, diag_name), stats in diagnostic_stats.items()
                        if diag_name == "Venus"
                    )
                    for key in ("generated", "viable")
                }
            try:
                solved = solve_alignment_members(group_index, next_remaining)
            finally:
                if name == "Mercury":
                    mercury_after = {
                        key: sum(
                            stats.get(key, 0)
                            for (diag_depth, diag_name), stats in diagnostic_stats.items()
                            if diag_name == "Venus"
                        )
                        for key in ("generated", "viable")
                    }
                    alignment_mercury_trials.append({
                        "signature": mercury_signature,
                        "box": (round(box.x, 2), round(box.y, 2), round(box.w, 2), round(box.h, 2)),
                        "venus_generated": mercury_after["generated"] - mercury_before["generated"],
                        "venus_viable": mercury_after["viable"] - mercury_before["viable"],
                    })
            if not solved:
                staged.pop(original_index, None)
                leader_names.pop()
                leaders.pop()
                placed.pop()
            return solved

        chosen_stream = viable_candidates(
            item, diagnostic_depth, consume_body_budget=False
        )
        try:
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
            # An alignment is viable only if the ordinary bodies can finish
            # the layout. Let a dead ordinary-body subtree backtrack into the
            # alignment layer instead of freezing its first complete plan.
            return search(0)
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
        nonlocal terminal_validation_checks, terminal_validation_rejections
        nonlocal terminal_validation_sun_leaders

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
                terminal_validation_checks += 1
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
                    terminal_validation_rejections += 1
                    for error in errors:
                        terminal_validation_errors[error] = terminal_validation_errors.get(error, 0) + 1
                        suffix = ": leader crosses Sun label"
                        if error.endswith(suffix):
                            leader_name = error[:-len(suffix)]
                            terminal_validation_sun_leaders[leader_name] = (
                                terminal_validation_sun_leaders.get(leader_name, 0) + 1
                            )
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
            pv_before = None
            uv_before = None
            if name == "Pluto" and depth + 1 < len(order) and order[depth + 1][1][1] == "Venus":
                venus_stats = diagnostic_stats.get((depth + 1, "Venus"), {})
                pv_before = {
                    key: venus_stats.get(key, 0)
                    for key in ("generated", "viable", "immutable_reserved", "immutable_rim",
                                "overlap", "leader_existing", "route", "leader_rim", "leader_graze")
                }
            if name == "Uranus" and depth + 1 < len(order) and order[depth + 1][1][1] == "Venus":
                venus_stats = diagnostic_stats.get((depth + 1, "Venus"), {})
                uv_before = {
                    key: venus_stats.get(key, 0)
                    for key in ("generated", "viable", "immutable_reserved", "immutable_rim",
                                "overlap", "leader_existing", "route", "leader_rim", "leader_graze")
                }
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

            if pv_before is not None:
                venus_stats = diagnostic_stats.get((depth + 1, "Venus"), {})
                delta = {
                    key: venus_stats.get(key, 0) - pv_before.get(key, 0)
                    for key in pv_before
                }
                pluto_venus_prefixes.append(delta)
            if uv_before is not None:
                venus_stats = diagnostic_stats.get((depth + 1, "Venus"), {})
                delta = {
                    key: venus_stats.get(key, 0) - uv_before.get(key, 0)
                    for key in uv_before
                }
                # Keep just enough parent geometry to distinguish whether the
                # same Uranus region repeatedly strands Venus. Pluto is still
                # present in placed[] at this point and is represented by the
                # enclosing DFS prefix; no search state is changed.
                delta["uranus_box"] = (round(box.x, 1), round(box.y, 1), round(box.w, 1), round(box.h, 1))
                delta["uranus_path"] = tuple((round(px, 1), round(py, 1)) for px, py in path)
                uranus_venus_prefixes.append(delta)
                if os.environ.get("PLANET_FINDER_FAST_VENUS_PROBE") == "1":
                    immutable = delta["immutable_reserved"] + delta["immutable_rim"]
                    placed_rejections = (delta["overlap"] + delta["leader_existing"] +
                                         delta["route"] + delta["leader_rim"] + delta["leader_graze"])
                    venus_stats = diagnostic_stats.get((depth + 1, "Venus"), {})
                    def ranked_blockers(key):
                        return ",".join(
                            f"{blocker}={count}"
                            for blocker, count in sorted(
                                venus_stats.get(key, {}).items(),
                                key=lambda item: (-item[1], item[0]),
                            )
                        ) or "-"
                    summary = (
                        f"FAST W36 VENUS PROBE: generated={delta['generated']} "
                        f"viable={delta['viable']} immutable={immutable} placed={placed_rejections} "
                        f"detail[reserved={delta['immutable_reserved']},rim={delta['immutable_rim']},"
                        f"overlap={delta['overlap']},leader={delta['leader_existing']},"
                        f"route={delta['route']},leader-rim={delta['leader_rim']},"
                        f"graze={delta['leader_graze']}] "
                        f"blockers[overlap={ranked_blockers('overlap_by_label')};"
                        f"existing-leader={ranked_blockers('existing_leader_by_name')};"
                        f"leader-graze={ranked_blockers('leader_graze_by_name')};"
                        f"own-label-graze={venus_stats.get('own_label_graze', 0)}] "
                        f"uranus_box={delta['uranus_box']} uranus_path={delta['uranus_path']}"
                    )
                    print(summary, flush=True)
                    raise RuntimeError("FAST_W36_VENUS_PROBE_COMPLETE")

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

    def search_coordinated_geometry():
        # Diagnostic-only escape hatch: skip the speculative alignment
        # preplanner and give recursive alignment backtracking the full mode
        # clock. Default is OFF, so production behavior is unchanged.
        if os.environ.get("PLANET_FINDER_SKIP_ALIGNMENT_PREPLANNER", "0") == "1":
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT PREPLANNER BYPASSED; "
                "starting recursive alignment layer directly",
                flush=True,
            )
            if alignment_group_items:
                return solve_alignment_group(0)
            return search(0)

        # Conjunctions have no placement path of their own.  Every body enters
        # the ordinary coordinated alignment planner; conjunction metadata is
        # consulted only by downstream backtracking to keep a conjunction
        # atomic when it must be reconsidered.
        alignment_preplacement = plan_alignment_layer()
        stage_alignment_preplacement(alignment_preplacement)
        return _search_alignment_fallback(
            alignment_preplacement, alignment_group_items, placed, leaders,
            leader_names, staged, search, solve_alignment_group,
        )

    try:
        solved = search_coordinated_geometry()
        exhausted = not solved
    except DepthNodeBudgetExhausted as exc:
        # Hitting the per-body/depth cap is the squeaky-wheel signal.  Report
        # this fixed ordering, then let layout() discard the whole DFS napkin
        # and retry from a clean state with that body promoted to first.
        dump_diagnostics(
            f"body-attempt-cap depth={exc.depth}/{len(order)} body={exc.name}"
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
