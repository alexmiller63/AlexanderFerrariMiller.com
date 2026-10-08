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


class ForwardBlockerExhausted(RuntimeError):
    """Signal that forward checking proved a child dead without its current parent."""

    def __init__(self, name: str):
        super().__init__(f"forward blocker exhausted for {name}")
        self.name = name


class DepthNodeBudgetExhausted(RuntimeError):
    """Signal that a body-depth node budget is exhausted for this DFS tree."""

    def __init__(self, depth: int, name: str):
        super().__init__(f"node budget exhausted at depth {depth} for {name}")
        self.depth = depth
        self.name = name

class SearchDeadlineExhausted(RuntimeError):
    """Signal that the absolute notation-mode wall clock has expired."""


class ForwardBlockerRepeated(RuntimeError):
    """Signal that one future body repeatedly kills otherwise viable prefixes."""

    def __init__(self, name: str, count: int):
        super().__init__(f"repeated forward blocker {name}: {count} dead prefixes")
        self.name = name
        self.count = count

import math
import os
import time



_DIAGNOSTIC_LEVEL = int(os.environ.get("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1"))


def diagnostic_print(*args, level=None, **kwargs):
    """Print Planet Finder diagnostics at the configured verbosity level.

    Level 0 is silent. Level 1 shows major controller events. Level 2 adds
    search-order and contest detail. Level 3 adds forensic terminal detail.
    Level 4 is a sparse solver trace: it suppresses the ordinary 1-3 stream
    and emits only high-value search-shape summaries already produced by the
    solver. It is diagnostic-only and never changes search behavior.
    """
    try:
        configured = max(0, int(os.environ.get("PLANET_FINDER_DIAGNOSTIC_LEVEL", str(_DIAGNOSTIC_LEVEL))))
    except ValueError:
        configured = 1

    text = " ".join(str(arg) for arg in args)

    if configured == 4:
        sparse_tokens = (
            "CAPPED SUMMARY",
            "REPEATED-DEAD-END STOP",
            "fixed-order summary",
            "FORWARD BLOCKER",
            "FORWARD REJECTION BREAKDOWN",
            "FORWARD BODY body=",
            "FORWARD BODY BLOCKERS",
            "SEARCH OUTCOME",
            "PROMOTE",
            "REFINEMENT",
            "deadline",
            "DEADLINE",
            "solution",
            "SOLUTION",
            "ALIGNMENT STATE REPETITION",
            "ALIGNMENT LAYER SHAPE",
            "ALIGNMENT LAST-MEMBER ZERO",
            "PRE-DFS TIMING alignment-fallback END",
        )
        if any(token in text for token in sparse_tokens):
            print(*args, **kwargs)
        return

    if level is None:
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
        except ForwardBlockerExhausted as exc:
            # A dead ordinary body under this complete alignment is evidence
            # against this alignment placement, not against the body globally.
            # Restore the planned blob and let recursive alignment DFS try a
            # sibling geometry.
            diagnostic_print(
                f"Planet Finder: ALIGNMENT PREPLACEMENT BLOCKED body={exc.name}; "
                "backtracking alignment blob",
                flush=True,
            )
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
        return solve_alignment_group(tuple(range(len(groups))))
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
    # Diagnostic-only ordinary DFS accounting.  This is intentionally separate
    # from candidate legality and budgets: it observes where the fixed-order
    # search spends its work without changing search order or pruning.
    dfs_forensics = {}
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
    refinement_timed_out = False
    terminal_validation_checks = 0
    terminal_validation_rejections = 0
    terminal_validation_errors = {}
    terminal_validation_sun_leaders = {}

    def check_deadline():
        """Interrupt any nested search work when the absolute mode clock expires."""
        if refinement_deadline is not None and time.monotonic() >= refinement_deadline:
            raise SearchDeadlineExhausted()

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
        for depth in sorted(set(depth_residence) | set(depth_visits) | set(dfs_forensics)):
            body_name = order[depth][1][1] if depth < len(order) else "complete-layout"
            forensic = dfs_forensics.get(depth, {})
            diagnostic_print(
                f"Planet Finder {mode}: TERMINAL DFS-TIME depth={depth}/{len(order)} "
                f"body={body_name} residence={depth_residence.get(depth, 0.0):.3f}s "
                f"visits={depth_visits.get(depth, 0):,} "
                f"admitted={forensic.get('admitted', 0):,} "
                f"forward-pass={forensic.get('forward_pass', 0):,} "
                f"forward-fail={forensic.get('forward_fail', 0):,} "
                f"child-calls={forensic.get('child_calls', 0):,} "
                f"child-success={forensic.get('child_success', 0):,} "
                f"backtracks={forensic.get('backtracks', 0):,} "
                f"subtree-time={forensic.get('subtree_time', 0.0):.3f}s "
                f"max-child-depth={forensic.get('max_child_depth', depth)}/{len(order)}",
                flush=True,
            )
        for (depth, name), r in sorted(route_diagnostics.items()):
            blockers = r.get("straight_blockers", {})
            obstacle_names = r.get("obstacle_names", [])
            named_blockers = {
                (obstacle_names[int(key.split("_", 1)[1])] if key.startswith("obstacle_") and int(key.split("_", 1)[1]) < len(obstacle_names) else key): count
                for key, count in blockers.items()
            }
            leader_names_diag = r.get("leader_names", [])
            directed_boxes = {
                (obstacle_names[i] if isinstance(i, int) and i < len(obstacle_names) else f"obstacle_{i}"): count
                for i, count in r.get("directed_box_by_index", {}).items()
            }
            directed_leaders = {
                (leader_names_diag[i] if isinstance(i, int) and i < len(leader_names_diag) else f"leader_{i}"): count
                for i, count in r.get("directed_leader_by_index", {}).items()
            }
            diagnostic_print(
                f"Planet Finder {mode}: TERMINAL ROUTE depth={depth}/{len(order)} body={name} "
                f"calls={r.get('route_calls', 0):,} success={r.get('route_succeeded', 0):,} "
                f"route_failed={r.get('route_failed', 0):,} recursive_nodes={r.get('recursive_nodes', 0):,} "
                f"max_nodes={r.get('max_recursive_nodes', 0):,} max_depth={r.get('max_route_depth', 0)} "
                f"node_cap={r.get('node_cap_hits', 0):,} depth_cap={r.get('depth_cap_hits', 0):,} "
                f"dead_hits={r.get('dead_state_hits', 0):,} landing_failed={r.get('landing_failed', 0):,} "
                f"bypass_blocked={r.get('bypass_blocked', 0):,} bypass_illegal={r.get('bypass_illegal', 0):,} "
                f"straight_blocked={r.get('straight_blocked', 0):,} anchor_blocked={r.get('anchor_blocked', 0):,} "
                f"dogleg_failed={r.get('dogleg_failed', 0):,} straight_blockers={named_blockers}",
                flush=True,
            )
            diagnostic_print(
                f"Planet Finder {mode}: TERMINAL ROUTE BLOCKERS depth={depth}/{len(order)} body={name} "
                f"directed_boxes={dict(sorted(directed_boxes.items(), key=lambda item: (-item[1], item[0]))[:12])} "
                f"directed_leaders={dict(sorted(directed_leaders.items(), key=lambda item: (-item[1], item[0]))[:12])}",
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
        ceres_attribution = {"overlap": {}, "existing-leader": {}, "leader-graze": {}}
        for (d, n), ds in diagnostic_stats.items():
            if n != "Ceres":
                continue
            for label, count in ds.get("overlap_by_label", {}).items():
                ceres_attribution["overlap"][label] = ceres_attribution["overlap"].get(label, 0) + count
            for label, count in ds.get("existing_leader_by_name", {}).items():
                ceres_attribution["existing-leader"][label] = ceres_attribution["existing-leader"].get(label, 0) + count
            for label, count in ds.get("leader_graze_by_name", {}).items():
                ceres_attribution["leader-graze"][label] = ceres_attribution["leader-graze"].get(label, 0) + count
        for kind, counts in ceres_attribution.items():
            top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:12]
            diagnostic_print(f"Planet Finder {mode}: CERES BLOCKERS kind={kind} " + (" ".join(f"{name}={count:,}" for name, count in top) if top else "none"), flush=True)
        ceres_attribution = {"overlap": {}, "existing-leader": {}, "leader-graze": {}}
        for (d, n), ds in diagnostic_stats.items():
            if n != "Ceres":
                continue
            for label, count in ds.get("overlap_by_label", {}).items():
                ceres_attribution["overlap"][label] = ceres_attribution["overlap"].get(label, 0) + count
            for label, count in ds.get("existing_leader_by_name", {}).items():
                ceres_attribution["existing-leader"][label] = ceres_attribution["existing-leader"].get(label, 0) + count
            for label, count in ds.get("leader_graze_by_name", {}).items():
                ceres_attribution["leader-graze"][label] = ceres_attribution["leader-graze"].get(label, 0) + count
        for kind, counts in ceres_attribution.items():
            top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:12]
            diagnostic_print(f"Planet Finder {mode}: CERES BLOCKERS kind={kind} " + (" ".join(f"{name}={count:,}" for name, count in top) if top else "none"), flush=True)
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
            check_deadline()
            # The cap is owned by the body, not by this generator instance or
            # this ordering. A body already at its persistent limit must not
            # receive one additional candidate merely because its ordering
            # changed.
            if consume_body_budget and body_attempts[name] >= budget["max_node_candidates"]:
                stats["blocked"] = "body-candidate-cap"
                diagnostic_print(
                    f"Planet Finder {mode}: BODY-CANDIDATE CAP order={order_index} "
                    f"depth={depth}/{len(order)} body={name} "
                    f"viable={body_candidates:,}/{budget['max_node_candidates']:,} "
                    f"unique_geometry={len(viable_geometry_seen.get(name, ())):,} "
                    f"cumulative_attempts={body_attempts[name]:,} "
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
                if name in ("Venus", "Ceres", "Uranus"):
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
                if name in ("Venus", "Ceres", "Uranus"):
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
            route_diag["leader_names"] = list(leader_names)
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
                existing_paths=leaders,
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
                if name in ("Venus", "Ceres", "Uranus"):
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
                    f"viable={body_candidates:,}/{budget['max_node_candidates']:,} "
                    f"unique_geometry={len(viable_geometry_seen.get(name, ())):,} "
                    f"cumulative_attempts={body_attempts[name]:,} "
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

    def plan_alignment_layer(groups=None, *, stagger=False):
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
                prior_paths = leaders + list(paths.values())
                path = route(
                    anchors[name], (x, y), reserved + placed + other_boxes,
                    allow_initial_escape_count=3,
                    target_box=chosen[name][2],
                    existing_paths=prior_paths,
                )
                label_hit = path is not None and any(
                    segment_hits_box(path[i], path[i + 1], box, PLACED_LABEL_LEADER_CLEARANCE)
                    for box in other_boxes for i in range(len(path) - 1)
                )
                rim_hit = path is not None and leader_hits_zodiac_rim(path)
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
                    longitude, w, h, reserved, displacement_scale, immutable_diag,
                    max_label_lengths=3.0,
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
            # Wide-first is an ordering policy, not a truncation policy.  Keep
            # every legal alternative so progressively narrower placements remain
            # available when the widest coordinated placements cannot finish.
            pools[name] = options
            if not pools[name]:
                return None

        # Preplan the whole crowded layer before DFS commits any one member.
        # Each close group gets simultaneous tangential slots wide enough for
        # the rendered labels plus the normal 14px inter-label clearance.
        # Candidate generation is unchanged; this only orders each member's
        # complete legal pool around its reserved slot, so ordinary
        # backtracking can still contract away from the wide plan.
        for names in group_names:
            if len(names) < 2:
                continue
            reference = longitudes[names[0]] - 90.0
            radius = max(1.0, float(RI - 5))
            widths_deg = {}
            for member in names:
                w, h = label_size(mode, member)
                tangential_px = max(float(w), float(h))
                widths_deg[member] = math.degrees(
                    2.0 * math.asin(min(1.0, tangential_px / (2.0 * radius)))
                )
            gap_deg = math.degrees(14.0 / radius)
            # Interleave crowded labels on two radial lanes. Their lane
            # separation must accommodate the rendered boxes, rather than
            # simply taking the next preferred radius (often only 45px away).
            # These are planning preferences; exact boxes and routes below
            # still decide whether the joint placement is legal.
            radial_lanes = tuple(PREFERRED_LABEL_RADII) + tuple(EXPANDED_LABEL_RADII)
            outer_radius = float(PREFERRED_LABEL_RADII[0])
            if stagger and len(names) >= 3:
                radial_clearance = max(max(label_size(mode, member)) for member in names)
                inner_limit = outer_radius - radial_clearance - LABEL_COLLISION_PADDING
                inner_radius = next((float(r) for r in radial_lanes if r <= inner_limit), None)
                if inner_radius is not None:
                    radial_lanes = (outer_radius, inner_radius)
                    # Each lane holds alternating members, so begin with half
                    # the single-ring angular footprint. Keep the normal gaps
                    # and all candidates: a tight preference never relaxes a
                    # collision check or freezes the plan during backtracking.
                    widths_deg = {member: width / 2.0 for member, width in widths_deg.items()}
            packed_deg = sum(widths_deg.values()) + gap_deg * (len(names) - 1)
            natural_angles = []
            for member in names:
                nx, ny = xy(longitudes[member], PREFERRED_LABEL_RADII[0])
                natural_angles.append(label_angle((nx, ny, None), reference))
            center = sum(natural_angles) / len(natural_angles)
            cursor = center - packed_deg / 2.0
            targets = {}
            for member in names:
                cursor += widths_deg[member] / 2.0
                targets[member] = cursor
                cursor += widths_deg[member] / 2.0 + gap_deg

            def angular_distance(a, b):
                return abs((a - b + 180.0) % 360.0 - 180.0)

            # Stagger the simultaneous wide plan across radial lanes instead
            # of forcing every label onto one ring.  These are real legal
            # candidates from the expanded +/-3-label-length planner lattice;
            # the complete compatible selection is staged before ordinary DFS.
            if not radial_lanes:
                radial_lanes = (RI - 90.0,)
            lane_targets = {}
            for index, member in enumerate(names):
                # Alternate outer/inner lanes first, then use deeper lanes for
                # larger groups.  This gives adjacent crowded labels different
                # radii while preserving the left-to-right astronomical order.
                lane_index = index % min(len(radial_lanes), 2)
                if len(names) > 4 and len(radial_lanes) > 2 and index >= 4:
                    lane_index = 2 + ((index - 4) % (len(radial_lanes) - 2))
                lane_targets[member] = float(radial_lanes[lane_index])

            for member in names:
                target = targets[member]
                target_radius = lane_targets[member]
                target_x, target_y = xy(target + reference, target_radius)
                pools[member].sort(
                    key=lambda row: (
                        # Rank against the actual staggered slot. Lexically
                        # preferring angle before radius effectively discards
                        # the radial lane whenever angles differ slightly.
                        (math.hypot(row[0] - target_x, row[1] - target_y)
                         if stagger else angular_distance(label_angle(row, reference), target)),
                        (0.0 if stagger else
                         abs(math.hypot(row[0] - CX, row[1] - CY) - target_radius)),
                        -math.hypot(
                            row[0] - xy(longitudes[member], PREFERRED_LABEL_RADII[0])[0],
                            row[1] - xy(longitudes[member], PREFERRED_LABEL_RADII[0])[1],
                        ),
                    )
                )
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT WIDE STAGGER PREPLAN variant={'spatial' if stagger else 'angular'} "
                f"members={names} packed={packed_deg:.2f}deg "
                f"targets={{{', '.join(f'{member}:{targets[member]:.2f}@r{lane_targets[member]:.1f}' for member in names)}}}",
                level=1, flush=True,
            )

        nodes = 0
        assign_visits = {}
        assign_rejects = {"empty_future": 0, "circular_order": 0, "planned_path": 0}
        deepest_alignment_choice = 0
        termination_reason = "exhausted"
        depth89 = {
            "depth8_entries": 0,
            "depth8_body": {},
            "depth8_candidate_tries": 0,
            "depth7_entries": 0,
            "depth7_parent_signatures": set(),
        }

        def assign(remaining, available, chosen):
            nonlocal nodes, deepest_alignment_choice, termination_reason
            depth_here = len(chosen)
            deepest_alignment_choice = max(deepest_alignment_choice, depth_here)
            assign_visits[depth_here] = assign_visits.get(depth_here, 0) + 1
            if not remaining:
                return (chosen, planned_paths(chosen))
            name = min(remaining, key=lambda candidate: (len(available[candidate]), order_names.index(candidate)))
            if depth_here == 8:
                depth89["depth8_entries"] += 1
                depth89["depth8_body"][name] = depth89["depth8_body"].get(name, 0) + 1
            elif depth_here == 7:
                depth89["depth7_entries"] += 1
                signature = tuple(
                    (member, round(chosen[member][0], 3), round(chosen[member][1], 3))
                    for member in sorted(chosen)
                )
                depth89["depth7_parent_signatures"].add(signature)
            others = [candidate for candidate in remaining if candidate != name]
            for row in available[name]:
                if depth_here == 8:
                    depth89["depth8_candidate_tries"] += 1
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
            f"- Depth 8/9 entries: {depth89['depth8_entries']:,}",
            f"- Depth 8/9 selected body: {depth89['depth8_body']}",
            f"- Depth 8/9 candidate tries: {depth89['depth8_candidate_tries']:,}",
            f"- Depth 7/9 entries: {depth89['depth7_entries']:,}",
            f"- Distinct depth 7 parent placements: {len(depth89['depth7_parent_signatures']):,}",
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
            f"rim={alignment_path_rejects['rim_hit']:,},graze={alignment_path_rejects['leader_graze']:,}] "
            f"depth8[entries={depth89['depth8_entries']:,},body={depth89['depth8_body']},"
            f"tries={depth89['depth8_candidate_tries']:,}] "
            f"depth7[entries={depth89['depth7_entries']:,},"
            f"distinct-parents={len(depth89['depth7_parent_signatures']):,}]",
            flush=True,
        )
        return result

    def predfs_rejection_snapshot():
        """Diagnostic-only aggregate of candidate work before ordinary DFS."""
        keys = (
            "generated", "viable", "immutable_reserved", "immutable_rim",
            "overlap", "leader_existing", "route", "leader_rim", "leader_graze",
        )
        return {
            key: sum(stats.get(key, 0) for stats in diagnostic_stats.values())
            for key in keys
        }

    def report_predfs_phase(label, before):
        after = predfs_rejection_snapshot()
        delta = {key: after[key] - before[key] for key in before}
        diagnostic_print(
            f"Planet Finder {mode}: PRE-DFS PHASE {label} "
            + " ".join(f"{key}={value:,}" for key, value in delta.items()),
            level=1, flush=True,
        )

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

    alignment_depth_forensics = {}
    alignment_phase_profile = {}
    # Candidate-position geometry depends only on the body, mode, immutable
    # reserved geometry, and displacement scale.  DFS prefixes affect the
    # filtering/routing that follows, not this proposal lattice.  Materialize
    # that invariant lattice once per body so repeated W17 final-pair probes
    # do not regenerate identical trigonometric/Box work.
    alignment_position_cache = {}

    def alignment_max_label_lengths(name):
        """Widen the candidate envelope only for crowded alignment groups."""
        group_size = next(
            (
                len(group)
                for group in alignment_group_items
                if any(member[1][1] == name for member in group)
            ),
            0,
        )
        if group_size >= 8:
            return 3.0
        if group_size >= 5:
            return 2.5
        return 2.0

    alignment_span_reported = set()

    def report_alignment_required_span(name):
        group = next((g for g in alignment_group_items if any(m[1][1] == name for m in g)), None)
        if not group or len(group) < 2:
            return
        key = tuple(m[1][1] for m in group)
        if key in alignment_span_reported:
            return
        alignment_span_reported.add(key)
        # Diagnostic only.  Convert each rendered label's tangential width at the
        # label radius into angular span, then add the same 14px separation used
        # by overlap checks between adjacent packed labels.
        radius = max(1.0, float(RI - 5))
        rows = []
        total_radians = 0.0
        for _, (_, member_name, _) in group:
            w, h = label_size(mode, member_name)
            tangential_px = max(float(w), float(h))
            radians = 2.0 * math.asin(min(1.0, tangential_px / (2.0 * radius)))
            rows.append((member_name, math.degrees(radians)))
            total_radians += radians
        total_radians += (len(group) - 1) * (14.0 / radius)
        packed_deg = math.degrees(total_radians)
        half_deg = packed_deg / 2.0
        envelope = alignment_max_label_lengths(name)
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT REQUIRED SPAN group-size={len(group)} "
            f"packed={packed_deg:.2f}deg half={half_deg:.2f}deg current-envelope={envelope:.2f} "
            f"ratio={half_deg / envelope:.2f} labels={rows!r}",
            level=1, flush=True,
        )

    def alignment_base_positions(item):
        _, (_, name, longitude) = item
        report_alignment_required_span(name)
        max_label_lengths = alignment_max_label_lengths(name)
        cache_key = (name, max_label_lengths)
        cached = alignment_position_cache.get(cache_key)
        if cached is None:
            w, h = label_size(mode, name)
            cached = tuple(
                legal_candidate_positions(
                    longitude, w, h, reserved, displacement_scale,
                    max_label_lengths=max_label_lengths,
                )
            )
            alignment_position_cache[cache_key] = cached
        return cached

    def alignment_geometry_candidates(item, pressure=None):
        """Cheap necessary-condition candidates for alignment look-ahead.

        This deliberately stops before leader routing.  It may admit geometries
        that the exact router later rejects, so it is safe only as a witness
        screen: absence proves impossibility; presence does not prove viability.
        """
        _, (_, name, longitude) = item
        for x, y, box in alignment_base_positions(item):
            if any(boxes_overlap(box, other, 14) for other in placed):
                continue
            if any(
                segment_hits_box(seg[i], seg[i + 1], box, 10)
                for seg in leaders
                for i in range(len(seg) - 1)
            ):
                continue
            if pressure is not None:
                pressure["geometry"] = pressure.get("geometry", 0) + 1
                anchor = xy(longitude, RI - 5)
                # Diagnostic only: a straight anchor-to-label segment that is
                # already too close to an existing leader is a cheap signal
                # that this apparent geometry choice will require routing.
                if leaders_too_close([anchor, (x, y)], leaders):
                    pressure["straight_conflict"] = pressure.get("straight_conflict", 0) + 1
                else:
                    pressure["straight_clear"] = pressure.get("straight_clear", 0) + 1
            yield box

    def alignment_profiled_candidates(item, depth, phase):
        """Diagnostic-only *exclusive* timing around viable_candidates.

        Time only next(stream) execution.  Do not charge recursive descendant
        work to a suspended generator after it yields a candidate.
        """
        body = item[1][1]
        key = (phase, body)
        row = alignment_phase_profile.setdefault(
            key, {"calls": 0, "elapsed": 0.0, "yielded": 0}
        )
        row["calls"] += 1
        stream = viable_candidates(item, depth, consume_body_budget=False)
        try:
            while True:
                started = time.monotonic()
                try:
                    candidate = next(stream)
                except StopIteration:
                    row["elapsed"] += time.monotonic() - started
                    break
                row["elapsed"] += time.monotonic() - started
                row["yielded"] += 1
                yield candidate
        finally:
            stream.close()

    def report_alignment_phase_profile():
        if alignment_routed_cache_stats:
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT ROUTED CACHE "
                + " | ".join(
                    f"{body}[lookups={stats['lookups']:,},hits={stats['hits']:,},"
                    f"misses={stats['misses']:,},unique={len(stats['unique_states']):,},"
                    f"stored={stats['stored']:,},beat-limited={stats['beat_limited']:,}]"
                    for body, stats in sorted(alignment_routed_cache_stats.items())
                ),
                level=1, flush=True,
            )
            for body, stats in sorted(alignment_routed_cache_stats.items()):
                if stats["beat_limited"]:
                    diagnostic_print(
                        f"Planet Finder {mode}: ALIGNMENT BEAT FORENSICS {body} "
                        f"limits={dict(sorted(stats['beat_limits'].items()))} "
                        f"state-shapes={dict(sorted(stats['state_shapes'].items()))}",
                        level=1, flush=True,
                    )
        if alignment_final_pair_domain_stats:
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT FINAL-PAIR REUSE "
                + " | ".join(
                    f"{body}[calls={stats['calls']:,},"
                    f"unique-domains={len(stats['domains']):,},"
                    f"repeated-domains={sum(count - 1 for count in stats['domains'].values() if count > 1):,},"
                    f"unique-candidates={len(stats['candidates']):,},"
                    f"candidate-reuses={sum(count - 1 for count in stats['candidates'].values() if count > 1):,}]"
                    for body, stats in sorted(alignment_final_pair_domain_stats.items())
                ),
                level=1, flush=True,
            )
        if alignment_final_pair_dependency_stats:
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT FINAL-PAIR DEPENDENCIES "
                + " | ".join(
                    f"{body}["
                    + ";".join(
                        f"{kind}=" + ",".join(
                            f"{name}:{count}" for name, count in sorted(values.items())
                            if name in ("Mercury", "Ceres")
                        )
                        for kind, values in stats.items()
                    )
                    + "]"
                    for body, stats in sorted(alignment_final_pair_dependency_stats.items())
                ),
                level=1, flush=True,
            )
        for body, stats in sorted(alignment_final_pair_domain_stats.items()):
            varying_by_domain = []
            for domain_sig, states in stats["domain_states"].items():
                if len(states) < 2:
                    continue
                names = sorted(set().union(*(state.keys() for state in states)))
                varying = [
                    name for name in names
                    if len({state.get(name) for state in states}) > 1
                ]
                varying_by_domain.append((len(states), varying))
            if varying_by_domain:
                diagnostic_print(
                    f"Planet Finder {mode}: ALIGNMENT FINAL-PAIR STATE VARIATION "
                    f"{body} "
                    + " | ".join(
                        f"repeats={repeats}:varying={','.join(varying) if varying else 'none'}"
                        for repeats, varying in sorted(varying_by_domain, reverse=True)
                    ),
                    level=1, flush=True,
                )
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT PHASE PROFILE "
            + " | ".join(
                f"{phase}:{body}[calls={row['calls']:,},yielded={row['yielded']:,},elapsed={row['elapsed']:.3f}s]"
                for (phase, body), row in sorted(alignment_phase_profile.items())
            ),
            level=1, flush=True,
        )

    def report_alignment_route_forensics():
        """Diagnostic-only attribution for pre-DFS routing failures."""
        rows = []
        aggregate = {}
        for (depth, body), diag in route_diagnostics.items():
            if depth >= 0:
                continue
            blockers = diag.get("straight_blockers", {})
            ranked = sorted(blockers.items(), key=lambda item: (-item[1], str(item[0])))
            obstacle_names = diag.get("obstacle_names", [])
            active_leaders = diag.get("leader_names", [])
            box_by_index = diag.get("directed_box_by_index", {})
            leader_by_index = diag.get("directed_leader_by_index", {})
            box_named = sorted(
                ((obstacle_names[i] if i < len(obstacle_names) else f"box_{i}", count)
                 for i, count in box_by_index.items()),
                key=lambda item: (-item[1], item[0]),
            )[:20]
            leader_named = sorted(
                ((active_leaders[i] if i < len(active_leaders) else f"leader_{i}", count)
                 for i, count in leader_by_index.items()),
                key=lambda item: (-item[1], item[0]),
            )[:20]
            failure_reasons = {
                key: diag.get(key, 0)
                for key in (
                    "anchor_blocked", "landing_failed", "directed_box_blocked",
                    "directed_leader_blocked", "bypass_blocked", "bypass_illegal",
                    "node_cap_hits", "depth_cap_hits", "dead_state_hits",
                    "recursive_nodes", "max_recursive_nodes", "max_route_depth",
                )
            }
            rows.append(
                (diag.get("route_failed", 0), body, depth,
                 diag.get("straight_blocked", 0), diag.get("elbows", {}), ranked[:12],
                 obstacle_names, active_leaders, box_named, leader_named, failure_reasons)
            )
            for blocker, count in blockers.items():
                aggregate[blocker] = aggregate.get(blocker, 0) + count
        for failed, body, depth, straight, elbows, blockers, obstacles, active_leaders, box_named, leader_named, failure_reasons in sorted(rows, reverse=True):
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT ROUTE FORENSIC "
                f"body={body} depth={depth} route_failed={failed:,} "
                f"straight_blocked={straight:,} blockers={blockers!r} "
                f"directed_boxes={box_named!r} directed_leaders={leader_named!r} "
                f"failure_reasons={failure_reasons!r} elbows={elbows!r} "
                f"active_leaders={active_leaders!r} obstacles={obstacles!r}",
                level=1, flush=True,
            )
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT ROUTE BLOCKERS AGGREGATE "
            + repr(sorted(aggregate.items(), key=lambda item: (-item[1], str(item[0])))[:30]),
            level=1, flush=True,
        )

    # Diagnostic only: measure how often alignment ranking re-evaluates the
    # same effective geometry. Never used to prune, cache, or reorder search.
    alignment_probe_signatures = {}
    # Diagnostic only: keep the alignment/member recursion separate from the
    # ordinary body DFS counters.  This makes a terminal nodes=0 unambiguous:
    # it can coexist with substantial pre-DFS alignment work.
    alignment_layer_entries = {}
    alignment_layer_probes = {}
    alignment_layer_tries = {}

    def report_alignment_layer_shape():
        keys = sorted(set(alignment_layer_entries) | set(alignment_layer_probes) | set(alignment_layer_tries))
        if not keys:
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT LAYER SHAPE none; ordinary-dfs-nodes={nodes:,}",
                level=1, flush=True,
            )
            return
        parts = []
        for group_index, depth_in_blob in keys:
            parts.append(
                f"g{group_index + 1}:d{depth_in_blob}["
                f"entries={alignment_layer_entries.get((group_index, depth_in_blob), 0):,},"
                f"probes={alignment_layer_probes.get((group_index, depth_in_blob), 0):,},"
                f"tries={alignment_layer_tries.get((group_index, depth_in_blob), 0):,}]"
            )
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT LAYER SHAPE "
            + " ".join(parts)
            + f" ordinary-dfs-nodes={nodes:,} ordinary-dfs-deepest={deepest}/{len(order)}",
            level=1, flush=True,
        )

    # Routed domains are deterministic for a fixed staged geometry.  MRV only
    # needs to distinguish an exact small domain from "at least the per-node
    # cap", while the immediately following DFS will try at most that same cap.
    # Cache both exhaustive domains and capped prefixes together with the cutoff
    # bit so repeated MRV probes never mistake a capped prefix for an exact
    # domain, and DFS can reuse the routed work ranking already paid for.
    alignment_routed_domain_cache = {}
    # Forward checking needs only an exact existence fact. Keep that fact
    # separate from routed domains so a one-witness probe can never truncate
    # the candidate stream later consumed by MRV/DFS.
    alignment_routed_existence_cache = {}
    # Diagnostic only: expose whether routed MRV work is genuinely reusable.
    # These counters never affect ranking, pruning, caching, or candidate order.
    alignment_routed_cache_stats = {}
    # Diagnostic only: fingerprint final-two routed domains independently of
    # the upstream state. This measures whether Venus/Uranus candidate geometry
    # actually repeats across distinct prefixes; it never changes search.
    alignment_final_pair_domain_stats = {}
    alignment_final_pair_dependency_stats = {}

    def final_pair_dependency_stat(body):
        return alignment_final_pair_dependency_stats.setdefault(
            body, {"overlap": {}, "existing_leader": {}, "route_box": {}, "route_leader": {}}
        )

    def candidate_geometry_signature(candidate):
        box, path = candidate
        return (
            (round(box.x, 2), round(box.y, 2), round(box.w, 2), round(box.h, 2)),
            tuple((round(x, 2), round(y, 2)) for x, y in path),
        )

    def routed_cache_stat(body):
        return alignment_routed_cache_stats.setdefault(
            body, {"lookups": 0, "hits": 0, "misses": 0,
                   "stored": 0, "beat_limited": 0,
                   "unique_states": set(), "beat_limits": {},
                   "state_shapes": {}}
        )

    def alignment_state_signature():
        def box_sig(box):
            return (round(box.x, 2), round(box.y, 2), round(box.w, 2), round(box.h, 2))
        def path_sig(path):
            return tuple((round(x, 2), round(y, 2)) for x, y in path)
        return (
            tuple(box_sig(box) for box in placed),
            tuple(path_sig(path) for path in leaders),
            tuple(leader_names),
        )

    def solve_alignment_members(group_index, remaining_items, on_complete):
        group_size = len(alignment_group_items[group_index])
        depth_in_blob = group_size - len(remaining_items)
        layer_key = (group_index, depth_in_blob)
        alignment_layer_entries[layer_key] = alignment_layer_entries.get(layer_key, 0) + 1
        if group_index == 0:
            key = (depth_in_blob, tuple(item[1][1] for item in remaining_items))
            row = alignment_depth_forensics.setdefault(
                key, {"entries": 0, "chosen": {}, "tries": 0, "forward_rejects": 0, "completions": 0,
                      "rank_seconds": 0.0, "chosen_viable": {}, "max_remaining": 0}
            )
            row["entries"] += 1
            row["max_remaining"] = max(row["max_remaining"], len(remaining_items))
        if not remaining_items:
            if group_index == 0:
                row["completions"] += 1
            # Atomic boundary: member DFS constructs one complete blob, then
            # hands that completed geometry to the outer group continuation.
            # A later-group failure returns here for the next COMPLETE blob
            # alternative; it never becomes a member of the later group's DFS.
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT BLOB CANDIDATE group={group_index + 1} complete",
                level=2, flush=True,
            )
            return on_complete()

        # Inner DFS for an alignment: choose the remaining member with the
        # fewest currently viable placements, then recurse. Alignment members
        # are ordinary backtrackable DFS choices; the alignment is not atomic.
        diagnostic_depth = -(group_index + 1)
        ranked = []
        rank_viable_counts = {}
        final_pair_route_pressure = {}
        best_count = None
        # Cheap geometry is a necessary-condition superset and costs almost
        # nothing compared with routing.  Use it only to decide which member
        # gets the first authoritative routed count.  Starting with the
        # smallest geometric domain usually establishes a tight beat before
        # expensive members such as Uranus are routed, allowing the routed
        # branch-and-bound below to stop them early.  Routed counts remain the
        # authoritative MRV values.
        geometry_ranked_items = []
        for candidate_item in remaining_items:
            geometry_probe = alignment_geometry_candidates(candidate_item)
            geometry_count = 0
            try:
                for _ in geometry_probe:
                    geometry_count += 1
                    if geometry_count >= budget["max_node_candidates"]:
                        break
            finally:
                geometry_probe.close()
            geometry_ranked_items.append((geometry_count, candidate_item))
        geometry_ranked_items.sort(key=lambda row: (row[0], row[1][0]))

        # General zero-domain propagation.  A cheap geometric zero is already
        # an exact impossibility because routed candidates are a subset of the
        # geometric domain.  Kill the prefix before paying for any routed MRV.
        geometric_zero = next(
            (candidate_item for geometry_count, candidate_item in geometry_ranked_items
             if geometry_count == 0),
            None,
        )
        if geometric_zero is not None:
            zero_name = geometric_zero[1][1]
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT MRV ZERO "
                f"group={group_index + 1} depth={depth_in_blob}/{group_size} "
                f"body={zero_name} source=geometry",
                level=1, flush=True,
            )
            return False

        # At the final pair, exact routed MRV ranking can consume the whole
        # mode clock before DFS visits a node. Geometry ranking is a safe
        # ordering heuristic here; the recursive DFS still performs the full
        # authoritative routed viability checks for both members.
        final_pair_geometry_rank = len(remaining_items) == 2

        for _, candidate_item in geometry_ranked_items:
            check_deadline()
            probe_name = candidate_item[1][1]
            probe_state = (group_index, depth_in_blob, probe_name, alignment_state_signature())
            alignment_probe_signatures[probe_state] = alignment_probe_signatures.get(probe_state, 0) + 1
            alignment_layer_probes[layer_key] = alignment_layer_probes.get(layer_key, 0) + 1
            probe_before = predfs_rejection_snapshot()
            probe_started = time.monotonic()
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT RANK PROBE START "
                f"group={group_index + 1} depth={depth_in_blob}/{group_size} "
                f"body={probe_name} remaining={len(remaining_items)} "
                f"beat={best_count if best_count is not None else 'none'}",
                level=1, flush=True,
            )
            # A/B diagnostic: at the final two-member alignment boundary,
            # rank with the authoritative routed domain instead of the cheap
            # geometry-only estimate. Tight-5 showed geometry claiming ~120
            # Venus choices while routed DFS had zero; this isolates whether
            # that false MRV signal is the complexity cliff.
            # MRV ranking must use the authoritative routed domain at every
            # alignment depth. The search is budgeted, so a cheaper
            # geometry-only ranking can change branch order and therefore
            # change which solution is reached before the budget expires.
            routed_rank = not final_pair_geometry_rank
            cached_rows = None
            cache_key = None
            if routed_rank:
                state_signature = alignment_state_signature()
                cache_key = (candidate_item[0], state_signature)
                cache_stat = routed_cache_stat(probe_name)
                cache_stat["lookups"] += 1
                cache_stat["unique_states"].add(state_signature)
                cached_rows = alignment_routed_domain_cache.get(cache_key)
                if cached_rows is None:
                    cache_stat["misses"] += 1
                else:
                    cache_stat["hits"] += 1
            # Beat-limited prefixes are lower bounds, never exact domains.
            full_rank_limit = budget["max_node_candidates"]
            rank_limit = full_rank_limit
            beat_limited = False
            if best_count is not None:
                rank_limit = min(full_rank_limit, best_count + 2)
                beat_limited = rank_limit < full_rank_limit
            if cached_rows is not None:
                cached_values, cutoff, cached_prefix = cached_rows
                if cached_prefix and len(cached_values) < rank_limit:
                    cached_rows = None
                    cache_stat["hits"] -= 1
                    cache_stat["misses"] += 1
                else:
                    cached_rows = cached_values
                    count = min(len(cached_values), rank_limit) if cached_prefix else len(cached_values)
            if cached_rows is None:
                if routed_rank:
                    probe = alignment_profiled_candidates(
                        candidate_item, diagnostic_depth, "alignment-rank-routed"
                    )
                else:
                    pressure = {}
                    probe = alignment_geometry_candidates(candidate_item, pressure)
                count = 0
                cutoff = False
                collected = [] if routed_rank else None
                # Branch-and-bound MRV: once an earlier member has an
                # exhaustive domain of N, this member only needs N+2 routed
                # witnesses to prove it lies outside the one-candidate
                # near-tie band.  Do not spend the rest of the 200-candidate
                # lattice proving an exact count that cannot change the choice.
                # A beat-limited prefix is intentionally not cached: if the
                # best count later changes, DFS may need the full domain.
                try:
                    for candidate in probe:
                        count += 1
                        if collected is not None:
                            collected.append(candidate)
                        if count >= rank_limit:
                            cutoff = True
                            break
                finally:
                    probe.close()
                if routed_rank:
                    cache_stat = routed_cache_stat(probe_name)
                    if beat_limited:
                        cache_stat["beat_limited"] += 1
                        cache_stat["beat_limits"][rank_limit] = (
                            cache_stat["beat_limits"].get(rank_limit, 0) + 1
                        )
                        state_shape = (len(placed), len(leaders), len(leader_names))
                        cache_stat["state_shapes"][state_shape] = (
                            cache_stat["state_shapes"].get(state_shape, 0) + 1
                        )
                        alignment_routed_domain_cache[cache_key] = (
                            tuple(collected), cutoff, True
                        )
                        cache_stat["stored"] += 1
                    else:
                        alignment_routed_domain_cache[cache_key] = (
                            tuple(collected), cutoff, False
                        )
                        cache_stat["stored"] += 1
            probe_elapsed = time.monotonic() - probe_started
            if len(remaining_items) == 2 and routed_rank:
                dep = final_pair_dependency_stat(probe_name)
                diag = route_diagnostics.get((diagnostic_depth, probe_name), {})
                obstacle_names = diag.get("obstacle_names", [])
                active_names = diag.get("leader_names", [])
                for idx, value in diag.get("directed_box_by_index", {}).items():
                    blocker = obstacle_names[idx] if idx < len(obstacle_names) else f"box_{idx}"
                    dep["route_box"][blocker] = value
                for idx, value in diag.get("directed_leader_by_index", {}).items():
                    blocker = active_names[idx] if idx < len(active_names) else f"leader_{idx}"
                    dep["route_leader"][blocker] = value
                body_diag = diagnostic_stats.get((diagnostic_depth, probe_name), {})
                dep["overlap"] = dict(body_diag.get("overlap_by_label", {}))
                dep["existing_leader"] = dict(body_diag.get("existing_leader_by_name", {}))
            probe_after = predfs_rejection_snapshot()
            probe_delta = {
                key: probe_after[key] - probe_before[key]
                for key in probe_before
            }
            pressure_text = ""
            if not routed_rank:
                geometry_count = pressure.get("geometry", 0)
                straight_conflict = pressure.get("straight_conflict", 0)
                straight_clear = pressure.get("straight_clear", 0)
                conflict_pct = (100.0 * straight_conflict / geometry_count if geometry_count else 0.0)
                if final_pair_geometry_rank:
                    final_pair_route_pressure[probe_name] = conflict_pct
                pressure_text = (
                    f" route-pressure[straight-clear={straight_clear:,},"
                    f"straight-conflict={straight_conflict:,},"
                    f"conflict-pct={conflict_pct:.1f}]"
                )
            # The geometry-only shadow is forensic instrumentation, not part of
            # the solver. Keep it available at diagnostic level 3, but do not
            # spend the normal search clock recomputing it for every routed MRV probe.
            shadow_count = None
            shadow_cutoff = False
            if int(os.environ.get("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")) >= 3:
                shadow_pressure = {}
                shadow_probe = alignment_geometry_candidates(candidate_item, shadow_pressure)
                shadow_count = 0
                try:
                    for _shadow_candidate in shadow_probe:
                        shadow_count += 1
                        if shadow_count >= budget["max_node_candidates"]:
                            shadow_cutoff = True
                            break
                finally:
                    shadow_probe.close()
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT RANK PROBE END "
                f"group={group_index + 1} depth={depth_in_blob}/{group_size} "
                f"body={probe_name} viable={count:,}{'+' if cutoff else ''} "
                f"pre-fix-geometry={shadow_count if shadow_count is not None else 'off'}"
                f"{'+' if shadow_cutoff else ''} "
                f"delta={(shadow_count - count) if shadow_count is not None else 'off'} "
                f"elapsed={probe_elapsed:.3f}s"
                f"{pressure_text} "
                + " ".join(
                    f"{key}={value:,}" for key, value in probe_delta.items()
                ),
                level=1, flush=True,
            )
            ranked.append((count, candidate_item))
            rank_viable_counts[probe_name] = (count, cutoff)
            # Diagnostic only: prove whether the routed MRV witness survives
            # unchanged into the authoritative DFS for the chosen member.
            # This is intentionally observational; it does not alter ranking,
            # caching, candidate order, or pruning.
            if routed_rank:
                forensic_cached = alignment_routed_domain_cache.get(cache_key)
                forensic_values = forensic_cached[0] if forensic_cached is not None else ()
                diagnostic_print(
                    f"Planet Finder {mode}: ALIGNMENT PROBE WITNESS "
                    f"group={group_index + 1} depth={depth_in_blob}/{group_size} "
                    f"body={probe_name} state={repr(cache_key[1])} "
                    f"cache={'hit' if forensic_cached is not None else 'miss'} "
                    f"cached={len(forensic_values)} "
                    f"prefix={forensic_cached[2] if forensic_cached is not None else 'none'} "
                    f"first={candidate_geometry_signature(forensic_values[0]) if forensic_values else 'none'}",
                    level=1, flush=True,
                )
            if len(remaining_items) == 2 and routed_rank and cached_rows is None:
                pair_stats = alignment_final_pair_domain_stats.setdefault(
                    probe_name, {"calls": 0, "domains": {}, "candidates": {},
                                 "domain_states": {}}
                )
                pair_stats["calls"] += 1
                domain_sig = tuple(
                    candidate_geometry_signature(candidate)
                    for candidate in (collected or ())
                )
                pair_stats["domains"][domain_sig] = pair_stats["domains"].get(domain_sig, 0) + 1
                state_by_name = {}
                for idx, placed_name in enumerate(leader_names):
                    state_by_name[placed_name] = (
                        (round(placed[idx].x, 2), round(placed[idx].y, 2),
                         round(placed[idx].w, 2), round(placed[idx].h, 2)),
                        tuple((round(x, 2), round(y, 2)) for x, y in leaders[idx]),
                    )
                pair_stats["domain_states"].setdefault(domain_sig, []).append(state_by_name)
                for candidate_sig in domain_sig:
                    pair_stats["candidates"][candidate_sig] = (
                        pair_stats["candidates"].get(candidate_sig, 0) + 1
                    )
            # An exhausted routed domain of zero is a complete proof that this
            # partial alignment prefix cannot be extended.  Propagate it here,
            # immediately, instead of carrying the zero through tie-breaking
            # and a later support/DFS layer.
            if count == 0 and not cutoff:
                diagnostic_print(
                    f"Planet Finder {mode}: ALIGNMENT MRV ZERO "
                    f"group={group_index + 1} depth={depth_in_blob}/{group_size} "
                    f"body={probe_name} source=routed",
                    level=1, flush=True,
                )
                return False
            if not cutoff and (best_count is None or count < best_count):
                best_count = count
                # Once an exact domain is known, restart ranking for the
                # remaining members under that beat.  The loop used to pay an
                # unbounded routed count for every member encountered before
                # the first tight domain (notably Uranus in W17).  A second
                # pass lets branch-and-bound cap those earlier probes too.
                if best_count == 0:
                    break
        # Near-tied MRV counts are not meaningfully different constraints.
        # Prefer the later member in the alignment sequence within a one-candidate
        # band so a fragile downstream member (notably Sun) is placed before a
        # one-choice predecessor can repeatedly destroy its last placements.
        if group_index == 0:
            row["rank_seconds"] += sum(
                alignment_phase_profile.get(("alignment-rank-routed", candidate_item[1][1]), {}).get("elapsed", 0.0)
                for candidate_item in ()
            )
        min_viable = min(row[0] for row in ranked)
        # Counts within one candidate are deliberately treated as tied.
        # Keep this narrow: widening the band at the final-three boundary made
        # W17 choose Uranus before Ceres and forced Ceres to be rerouted for
        # every Uranus sibling (about 15s versus about 1.2s with Ceres first).
        near_tied = [
            row for row in ranked if row[0] <= min_viable + 1
        ]
        # Zero is a proof of failure and must always win. Otherwise all
        # members inside the near-tie band are deliberately treated as tied,
        # so choose the later alignment member first.
        zero_rows = [row for row in near_tied if row[0] == 0]
        if zero_rows:
            viable_count, item = min(zero_rows, key=lambda row: row[1][0])
        elif final_pair_geometry_rank:
            # Fail first on the harder-to-route member when the final two
            # geometric domains are tied. This avoids rerouting that expensive
            # member beneath every sibling of the easier member.
            viable_count, item = max(
                near_tied,
                key=lambda row: (
                    final_pair_route_pressure.get(row[1][1][1], 0.0),
                    row[1][0],
                ),
            )
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT FINAL-PAIR PRESSURE CHOICE "
                f"member={item[1][1]} geometry={viable_count} "
                f"conflict-pct={final_pair_route_pressure.get(item[1][1], 0.0):.1f}",
                level=1, flush=True,
            )
        else:
            viable_count, item = max(near_tied, key=lambda row: row[1][0])
        original_index, (symbol, name, longitude) = item
        if group_index == 0:
            row["chosen"][name] = row["chosen"].get(name, 0) + 1
            viable_key = f"{name}:{viable_count}{'+' if rank_viable_counts.get(name, (0, False))[1] else ''}"
            row["chosen_viable"][viable_key] = row["chosen_viable"].get(viable_key, 0) + 1
        next_remaining = [candidate_item for candidate_item in remaining_items if candidate_item is not item]
        tried = 0
        # Keep a dead final alignment member from monopolizing the mode clock.
        # After 200 sibling choices, return to its parent so the blob geometry
        # itself can move; this restores the intended per-body squeaky-wheel cap.
        candidate_limit = min(budget["max_node_candidates"], 200)
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT INNER DFS CHOOSE group={group_index + 1} "
            f"member={name} viable={viable_count} remaining={len(remaining_items)}",
            level=1, flush=True,
        )
        if viable_count == 0:
            if len(remaining_items) == 1:
                ds = diagnostic_stats.get((diagnostic_depth, name), {})
                diagnostic_print(
                    f"Planet Finder {mode}: ALIGNMENT LAST-MEMBER ZERO "
                    f"group={group_index + 1} depth={depth_in_blob}/{group_size} body={name} "
                    f"rejects[immutable-reserved={ds.get('immutable_reserved', 0):,},"
                    f"immutable-rim={ds.get('immutable_rim', 0):,},"
                    f"placed-overlap={ds.get('overlap', 0):,},"
                    f"existing-leader={ds.get('leader_existing', 0):,},"
                    f"route={ds.get('route', 0):,},"
                    f"leader-rim={ds.get('leader_rim', 0):,},"
                    f"leader-graze={ds.get('leader_graze', 0):,}] "
                    f"overlap_by={sorted(ds.get('overlap_by_label', {}).items(), key=lambda x: (-x[1], x[0]))[:8]} "
                    f"leader_by={sorted(ds.get('existing_leader_by_name', {}).items(), key=lambda x: (-x[1], x[0]))[:8]} "
                    f"graze_by={sorted(ds.get('leader_graze_by_name', {}).items(), key=lambda x: (-x[1], x[0]))[:8]}",
                    level=1, flush=True,
                )
            return False

        # Arc-consistency gate inside the alignment blob.  When the chosen MRV
        # member has a small exhaustive domain, every one of its candidates
        # must have support in every remaining blob member.  If none does, the
        # chosen member's effective domain is zero and this upstream prefix is
        # proven dead before expensive ordinary-body propagation.
        chosen_count, chosen_capped = rank_viable_counts.get(name, (viable_count, True))
        support_limit = max(
            1, int(os.environ.get("PLANET_FINDER_ALIGNMENT_SUPPORT_LIMIT", "8"))
        )
        # Do not pre-prove support when exactly one alignment member remains.
        # The recursive member DFS immediately performs that same authoritative
        # routed search. W17 showed this duplicate final-pair proof being paid
        # hundreds of times (especially Moon/Uranus) without opening new geometry.
        if len(next_remaining) > 1 and not chosen_capped and chosen_count <= support_limit:
            support_stream = alignment_profiled_candidates(
                item, diagnostic_depth, "alignment-support"
            )
            supported = False
            try:
                for support_candidate in support_stream:
                    check_deadline()
                    support_box, support_path = support_candidate
                    placed.append(support_box)
                    leaders.append(support_path)
                    leader_names.append(name)
                    staged[original_index] = (
                        symbol, name, longitude, support_box, support_path
                    )
                    try:
                        candidate_supported = True
                        for future_item in next_remaining:
                            # Cheap necessary-condition support remains sufficient
                            # here. Authoritative routed viability is already computed
                            # by MRV; do not pay for the same routed proof twice.
                            final_pair_support = len(next_remaining) == 1
                            witness_stream = (
                                alignment_profiled_candidates(
                                    future_item,
                                    diagnostic_depth,
                                    "alignment-final-pair-support",
                                )
                                if final_pair_support
                                else alignment_geometry_candidates(future_item)
                            )
                            try:
                                next(witness_stream)
                            except StopIteration:
                                candidate_supported = False
                            finally:
                                witness_stream.close()
                            if not candidate_supported:
                                break
                        if candidate_supported:
                            supported = True
                            break
                    finally:
                        staged.pop(original_index, None)
                        leader_names.pop()
                        leaders.pop()
                        placed.pop()
            finally:
                support_stream.close()
            if not supported:
                return False

        def alignment_pair_compatible():
            """Safely reject a prefix only from a cheap exhaustive pair proof.

            First screen each unstaged ordinary body only far enough to discover
            genuinely small candidate sets. If no body exhausts within the
            screen, preserve the prefix (UNKNOWN) instead of spending time on
            exact ranking. If a body does exhaust, every one of its candidates
            is tested against a second ordinary body. False therefore remains
            an exhaustive incompatibility proof; all uncertain cases return True.
            """
            ordinary = [item for item in order if item[0] not in staged]
            if len(ordinary) < 2:
                return True

            screen_limit = max(
                1, int(os.environ.get("PLANET_FINDER_ALIGNMENT_PAIR_SCREEN_LIMIT", "8"))
            )
            screened = []
            pair_probe_started = time.monotonic()
            pair_probe_body_times = []

            for ordinary_item in ordinary:
                check_deadline()
                ordinary_probe_started = time.monotonic()
                probe = alignment_profiled_candidates(
                    ordinary_item, len(order), "pair-probe"
                )
                candidates = []
                capped = False
                try:
                    for candidate in probe:
                        if len(candidates) >= screen_limit:
                            capped = True
                            break
                        candidates.append(candidate)
                finally:
                    probe.close()
                ordinary_probe_elapsed = time.monotonic() - ordinary_probe_started
                pair_probe_body_times.append((ordinary_item[1][1], ordinary_probe_elapsed))
                screened.append((len(candidates), capped, ordinary_item, candidates))

            pair_probe_elapsed = time.monotonic() - pair_probe_started
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT PAIR SCREEN "
                + " ".join(
                    f"{row[2][1][1]}=count:{row[0]},capped:{row[1]}"
                    for row in screened
                )
                + f" screen_limit={screen_limit}"
                + f" probe_elapsed={pair_probe_elapsed:.3f}s"
                + " body_times="
                + ",".join(f"{body}:{elapsed:.3f}s" for body, elapsed in pair_probe_body_times),
                level=1, flush=True,
            )

            exact = [row for row in screened if not row[1]]
            if not exact:
                diagnostic_print(
                    f"Planet Finder {mode}: ALIGNMENT PAIR UNKNOWN "
                    f"reason=no-small-exhaustive-body screen_limit={screen_limit} "
                    f"probe_elapsed={pair_probe_elapsed:.3f}s",
                    level=2, flush=True,
                )
                return True

            exact.sort(key=lambda row: (row[0], row[2][0]))
            first_row = exact[0]
            first = first_row[2]
            first_candidates = first_row[3]

            # Pair selection is only a heuristic. Prefer another exact small
            # body when available; otherwise choose the earliest deterministic
            # remaining body. Correctness comes from exhaustively testing every
            # first-body candidate, not from how the second body is selected.
            remaining_rows = [row for row in screened if row[2] is not first]
            exact_seconds = [row for row in remaining_rows if not row[1]]
            if exact_seconds:
                exact_seconds.sort(key=lambda row: (row[0], row[2][0]))
                second = exact_seconds[0][2]
            else:
                remaining_rows.sort(key=lambda row: row[2][0])
                second = remaining_rows[0][2]

            first_index, (first_symbol, first_name, first_longitude) = first
            second_name = second[1][1]
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT PAIR PROOF "
                f"first={first_name} second={second_name} "
                f"first-count={len(first_candidates)} "
                f"placed={len(placed)} leaders={len(leaders)} staged={len(staged)}",
                level=1, flush=True,
            )

            tested = 0
            pair_witness_calls = 0
            pair_witness_elapsed = 0.0
            for first_box, first_path in first_candidates:
                check_deadline()
                tested += 1
                placed.append(first_box)
                leaders.append(first_path)
                leader_names.append(first_name)
                staged[first_index] = (
                    first_symbol, first_name, first_longitude,
                    first_box, first_path,
                )
                try:
                    second_stream = alignment_profiled_candidates(
                        second, len(order), "pair-witness"
                    )
                    witness_started = time.monotonic()
                    pair_witness_calls += 1
                    try:
                        next(second_stream)
                    except StopIteration:
                        pass
                    else:
                        diagnostic_print(
                            f"Planet Finder {mode}: ALIGNMENT PAIR WITNESS "
                            f"first={first_name} second={second_name} tested={tested} "
                            f"probe_elapsed={pair_probe_elapsed:.3f}s "
                            f"witness_calls={pair_witness_calls} "
                            f"witness_elapsed={pair_witness_elapsed:.3f}s "
                            f"pair_elapsed={time.monotonic() - pair_probe_started:.3f}s",
                            level=2, flush=True,
                        )
                        return True
                    finally:
                        pair_witness_elapsed += time.monotonic() - witness_started
                        second_stream.close()
                finally:
                    staged.pop(first_index, None)
                    leader_names.pop()
                    leaders.pop()
                    placed.pop()

            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT PAIR BACKTRACK "
                f"first={first_name} second={second_name} tested={tested} "
                f"first-count={len(first_candidates)} "
                f"probe_elapsed={pair_probe_elapsed:.3f}s "
                f"witness_calls={pair_witness_calls} "
                f"witness_elapsed={pair_witness_elapsed:.3f}s "
                f"pair_elapsed={time.monotonic() - pair_probe_started:.3f}s "
                f"reason=no-compatible-pair",
                level=1, flush=True,
            )
            return False

        same_blob_failure_states = {}

        def alignment_state_fingerprint():
            """Stable geometric identity for diagnostic comparison of staged prefixes."""
            return tuple(
                (
                    staged_item[1],
                    round(staged_item[3].x, 3),
                    round(staged_item[3].y, 3),
                    round(staged_item[3].w, 3),
                    round(staged_item[3].h, 3),
                    tuple(
                        (round(px, 3), round(py, 3))
                        for px, py in staged_item[4]
                    ),
                )
                for _, staged_item in sorted(staged.items())
            )

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
                # Forensic: the final Group-1 Mercury choice has no remaining
                # blob members. Track whether it reaches the ordinary-body
                # witness gate and, if rejected, which ordinary body proves it
                # dead. Diagnostic only; search behavior is unchanged.
                final_mercury = (
                    group_index == 0 and name == "Mercury" and not next_remaining
                )
                mercury_final_blocker = None
                alignment_forward_ok = True

                # Do not run a separate exhaustive three-member forward proof here.
                # The alignment member DFS immediately below searches the same routed
                # continuation exactly.  On W01 tight-5 this look-ahead consumed the
                # entire 60s wall clock proving 100+ Mars prefixes dead before the
                # real DFS could advance.  Removing the redundant proof changes only
                # pruning/order, not the set of layouts accepted by the exact DFS.

                # Likewise, do not exhaustively prove the final two-member
                # continuation before descending.  The exact member DFS below
                # performs that same routed pair search.  In W01 tight-5 this
                # redundant parent-pair proof consumed nearly the entire wall
                # clock after the analogous triple proof was removed.

                # Do not speculatively forward-probe remaining alignment
                # members here. The recursive alignment DFS immediately below
                # performs the same routed continuation authoritatively. W17
                # diagnostics showed these redundant existence probes dominated
                # the mode clock (especially Moon alignment-forward). Removing
                # them changes pruning only, not geometry or accepted layouts.
                # Do not run the ordinary-body pair proof here.  It is a
                # speculative look-ahead across the alignment/ordinary boundary;
                # the exact DFS below will test those ordinary placements when
                # the alignment prefix completes.  In W01 tight-5 its bounded
                # probes (especially Jupiter and Saturn) became a major wall-clock
                # cost without changing which complete layouts are accepted.
                if not alignment_forward_ok:
                    if final_mercury:
                        diagnostic_print(
                            f"Planet Finder {mode}: FINAL MERCURY FORENSIC "
                            f"result=REJECT ordinary-blocker={mercury_final_blocker or 'same-blob'}",
                            level=1, flush=True,
                        )
                    solved = False
                else:
                    if final_mercury:
                        diagnostic_print(
                            f"Planet Finder {mode}: FINAL MERCURY FORENSIC "
                            f"result=PASS ordinary-witness-gate",
                            level=1, flush=True,
                        )
                    solved = solve_alignment_members(group_index, next_remaining, on_complete)
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

        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT DFS ENTER group={group_index + 1} "
            f"member={name} remaining={len(remaining_items)}",
            level=1, flush=True,
        )
        chosen_cache_key = (item[0], alignment_state_signature())
        chosen_cached = alignment_routed_domain_cache.get(chosen_cache_key)
        chosen_values = chosen_cached[0] if chosen_cached is not None else ()
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT DFS WITNESS "
            f"group={group_index + 1} depth={depth_in_blob}/{group_size} "
            f"member={name} state={repr(chosen_cache_key[1])} "
            f"ranked={rank_viable_counts.get(name)} "
            f"cache={'hit' if chosen_cached is not None else 'miss'} "
            f"cached={len(chosen_values)} "
            f"prefix={chosen_cached[2] if chosen_cached is not None else 'none'} "
            f"first={candidate_geometry_signature(chosen_values[0]) if chosen_values else 'none'}",
            level=1, flush=True,
        )
        chosen_stream = (
            iter(chosen_cached[0])
            if chosen_cached is not None
            else alignment_profiled_candidates(item, diagnostic_depth, "alignment-dfs")
        )
        chosen_count, chosen_capped = rank_viable_counts.get(
            name, (viable_count, True)
        )
        # Do not pre-prove support at the final pair. The recursive
        # alignment DFS immediately performs that exact routed search, so a
        # support probe here duplicates the expensive zero-domain proof before
        # doing the same work again. Keep the small-domain support gate only
        # before the final binary choice.
        final_pair = len(remaining_items) == 2
        exact_support_filter = (
            bool(next_remaining)
            and not final_pair
            and not chosen_capped
            and chosen_count <= support_limit
        )
        try:
            for candidate in chosen_stream:
                if exact_support_filter:
                    box, path = candidate
                    placed.append(box)
                    leaders.append(path)
                    leader_names.append(name)
                    staged[original_index] = (
                        symbol, name, longitude, box, path
                    )
                    try:
                        has_exact_support = True
                        support_items = list(next_remaining)
                        # Body-agnostic support ordering: use the routed MRV
                        # information already computed for this state.  A future
                        # member with the smallest known domain is the likeliest
                        # cheap contradiction, so test it first.  This changes
                        # proof order only; every required support witness is
                        # still checked before the candidate is admitted.
                        support_items.sort(
                            key=lambda future_item: (
                                rank_viable_counts.get(
                                    future_item[1][1],
                                    (budget["max_node_candidates"] + 1, True),
                                )[0],
                                future_item[0],
                            )
                        )
                        for future_item in support_items:
                            witness_stream = alignment_profiled_candidates(
                                future_item,
                                diagnostic_depth,
                                "alignment-exact-support",
                            )
                            try:
                                next(witness_stream)
                            except StopIteration:
                                has_exact_support = False
                            finally:
                                witness_stream.close()
                            if not has_exact_support:
                                break
                    finally:
                        staged.pop(original_index, None)
                        leader_names.pop()
                        leaders.pop()
                        placed.pop()
                    if not has_exact_support:
                        continue

                tried += 1
                alignment_layer_tries[layer_key] = alignment_layer_tries.get(layer_key, 0) + 1
                if group_index == 0:
                    row["tries"] += 1
                if try_candidate(candidate):
                    return True
                if tried >= candidate_limit:
                    break
        finally:
            close_chosen = getattr(chosen_stream, "close", None)
            if close_chosen is not None:
                close_chosen()
        if group_index == 0 and tried > 0:
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT DEPTH FORENSIC "
                f"group=1 depth={depth_in_blob}/{group_size} member={name} "
                f"entries={row['entries']:,} tries={row['tries']:,} "
                f"completions={row['completions']:,}",
                level=1, flush=True,
            )
        if name == "Mercury" and tried == 0:
            ds = diagnostic_stats.get((diagnostic_depth, name), {})
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT MERCURY ZERO "
                f"reserved={ds.get('immutable_reserved', 0)} rim={ds.get('immutable_rim', 0)} "
                f"overlap={ds.get('overlap', 0)} existing-leader={ds.get('leader_existing', 0)} "
                f"route={ds.get('route', 0)} leader-rim={ds.get('leader_rim', 0)} "
                f"leader-graze={ds.get('leader_graze', 0)}",
                level=1, flush=True,
            )
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT DFS EXHAUSTED group={group_index + 1} "
            f"member={name} tried={tried}",
            level=1, flush=True,
        )
        return False

    def forensic_uranus_venus_boundary():
        """Diagnostic-only compatibility snapshot for the W36 Uranus/Venus boundary."""
        if not context_label or "uranus-venus" not in context_label:
            return
        by_name = {item[1][1]: item for item in order}
        if "Uranus" not in by_name or "Venus" not in by_name:
            return

        def probe(body_name, limit=32):
            item = by_name[body_name]
            before = {}
            for (diag_depth, diag_name), ds in diagnostic_stats.items():
                if diag_name == body_name:
                    for key in ("overlap", "leader_existing", "route", "leader_graze"):
                        before[key] = before.get(key, 0) + ds.get(key, 0)
            stream = viable_candidates(item, len(order), consume_body_budget=False)
            rows = []
            exhausted = True
            try:
                for box, path in stream:
                    rows.append((box, path))
                    if len(rows) >= limit:
                        exhausted = False
                        break
            finally:
                stream.close()
            after = {}
            blockers = {"overlap": {}, "existing": {}, "graze": {}}
            for (diag_depth, diag_name), ds in diagnostic_stats.items():
                if diag_name != body_name:
                    continue
                for key in ("overlap", "leader_existing", "route", "leader_graze"):
                    after[key] = after.get(key, 0) + ds.get(key, 0)
                for src, dst in (
                    ("overlap_by_label", blockers["overlap"]),
                    ("existing_leader_by_name", blockers["existing"]),
                    ("leader_graze_by_name", blockers["graze"]),
                ):
                    for name, count in ds.get(src, {}).items():
                        dst[name] = dst.get(name, 0) + count
            delta = {key: after.get(key, 0) - before.get(key, 0) for key in ("overlap", "leader_existing", "route", "leader_graze")}
            top = lambda d: ",".join(f"{name}:{count}" for name, count in sorted(d.items(), key=lambda row: (-row[1], row[0]))[:4]) or "none"
            diagnostic_print(
                f"Planet Finder {mode}: UV BOUNDARY body={body_name} viable={len(rows)}"
                f"{'' if exhausted else '+'} rejects[overlap={delta['overlap']},existing={delta['leader_existing']},route={delta['route']},graze={delta['leader_graze']}] "
                f"blockers[overlap={top(blockers['overlap'])};existing={top(blockers['existing'])};graze={top(blockers['graze'])}]",
                level=1, flush=True,
            )
            return rows, exhausted

        u_rows, _ = probe("Uranus")
        v_rows, _ = probe("Venus")

        def directional(first_name, first_rows, second_name):
            first_item = by_name[first_name]
            first_index, (symbol, name, longitude) = first_item
            compatible = 0
            tested = 0
            for box, path in first_rows:
                tested += 1
                placed.append(box)
                leaders.append(path)
                leader_names.append(name)
                staged[first_index] = (symbol, name, longitude, box, path)
                try:
                    stream = viable_candidates(by_name[second_name], len(order), consume_body_budget=False)
                    try:
                        next(stream)
                    except StopIteration:
                        pass
                    else:
                        compatible += 1
                    finally:
                        stream.close()
                finally:
                    staged.pop(first_index, None)
                    leader_names.pop()
                    leaders.pop()
                    placed.pop()
            diagnostic_print(
                f"Planet Finder {mode}: UV COMPAT first={first_name} second={second_name} "
                f"tested={tested} compatible={compatible} incompatible={tested-compatible}",
                level=1, flush=True,
            )

        directional("Uranus", u_rows, "Venus")
        directional("Venus", v_rows, "Uranus")

    # Cache bounded blob-domain probes by exact staged geometry. Look-ahead
    # and authoritative recursion frequently ask the identical question; the
    # answer is deterministic for a fixed staged state and probe limit.
    def solve_alignment_group(remaining_group_indices):
        """Solve alignment blobs with cheap fail-first ordering and exact DFS."""
        if not remaining_group_indices:
            alignment_indices = {
                item[0]
                for group in alignment_group_items
                for item in group
            }
            rows = [
                staged[index]
                for index in alignment_indices
                if index in staged
            ]
            valid, errors = validate_layout(mode, rows)
            if not valid:
                diagnostic_print(
                    f"Planet Finder {mode}: ALIGNMENT RECURSIVE BACKTRACK "
                    f"group=complete reason=layout "
                    f"example={errors[0] if errors else 'unknown'}",
                    level=1, flush=True,
                )
                return False

            forensic_uranus_venus_boundary()
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT RECURSIVE HANDOFF "
                f"preplaced={'|'.join(leader_names)} ordinary={len(order)}",
                level=1, flush=True,
            )
            search_started = time.monotonic()
            try:
                solved = search(0)
            except ForwardBlockerExhausted:
                solved = False
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT RECURSIVE RETURN "
                f"solved={solved} elapsed={time.monotonic() - search_started:.3f}s "
                f"preplaced={'|'.join(leader_names)}",
                level=1, flush=True,
            )
            return solved

        # Cheap blob MRV: estimate each blob by its tightest member in the
        # current geometry. This is ordering only; it never proves or prunes a
        # whole blob. Exact member DFS below remains authoritative.
        #
        # Level-4 forensics time this pre-DFS ranking separately. W20's
        # seven-member cliff can otherwise consume the entire mode clock here
        # while the ordinary DFS correctly reports nodes=0, obscuring which
        # group/member owns the candidate-generation cost.
        blob_ranked = []
        rank_started = time.monotonic()
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT GROUP RANK START "
            f"remaining={tuple(index + 1 for index in remaining_group_indices)} "
            f"preplaced={'|'.join(leader_names) or 'none'}",
            level=4, flush=True,
        )
        for candidate_group_index in remaining_group_indices:
            check_deadline()
            member_counts = []
            group_rank_started = time.monotonic()
            for item in alignment_group_items[candidate_group_index]:
                member_started = time.monotonic()
                stream = alignment_profiled_candidates(
                    item,
                    -(candidate_group_index + 1),
                    "alignment-group-rank",
                )
                count = 0
                try:
                    for _ in stream:
                        check_deadline()
                        count += 1
                        if count >= budget["max_node_candidates"]:
                            break
                finally:
                    stream.close()
                member_counts.append(count)
                diagnostic_print(
                    f"Planet Finder {mode}: ALIGNMENT GROUP RANK MEMBER "
                    f"group={candidate_group_index + 1} body={item[1][1]} "
                    f"candidates={count} elapsed={time.monotonic() - member_started:.3f}s",
                    level=4, flush=True,
                )
                if count == 0:
                    break
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT GROUP RANK GROUP "
                f"group={candidate_group_index + 1} counts={member_counts} "
                f"elapsed={time.monotonic() - group_rank_started:.3f}s",
                level=4, flush=True,
            )
            blob_ranked.append((
                min(member_counts) if member_counts else 0,
                candidate_group_index,
            ))
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT GROUP RANK END "
            f"elapsed={time.monotonic() - rank_started:.3f}s "
            f"ranks={[(index + 1, count) for count, index in blob_ranked]}",
            level=4, flush=True,
        )

        # At blob level, prefer the larger constraint footprint: placing
        # the broader blob first exposes its restrictions to the remaining
        # blobs instead of repeatedly embedding it under a narrow blob.
        _, group_index = max(blob_ranked, key=lambda row: (row[0], -row[1]))
        group_items = alignment_group_items[group_index]
        group_names = ">".join(item[1][1] for item in group_items)
        next_groups = tuple(
            index for index in remaining_group_indices if index != group_index
        )
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT GROUP MRV "
            f"chosen={group_index + 1} members={group_names} "
            f"remaining={len(remaining_group_indices)} "
            f"ranks={[(index + 1, count) for count, index in blob_ranked]}",
            level=1, flush=True,
        )
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT RECURSIVE ENTER "
            f"group={group_index + 1}/{len(alignment_group_items)} "
            f"members={group_names} preplaced={'|'.join(leader_names) or 'none'}",
            level=1, flush=True,
        )

        completions = 0

        def remaining_blob_has_witness(candidate_group_index):
            """Cheap forward check: stop at the first complete blob witness."""
            candidate_items = list(alignment_group_items[candidate_group_index])

            def witness_members(remaining_items):
                check_deadline()
                if not remaining_items:
                    return True

                # This is an existence query, not an MRV/domain measurement.
                # Preserve the blob's established member order and search
                # lazily; candidate generation is already widest-first.
                item = remaining_items[0]
                original_index, (symbol, name, longitude) = item
                next_remaining = remaining_items[1:]
                stream = alignment_profiled_candidates(
                    item,
                    -(candidate_group_index + 1),
                    "alignment-blob-forward-witness",
                )
                try:
                    for box, path in stream:
                        placed.append(box)
                        leaders.append(path)
                        leader_names.append(name)
                        staged[original_index] = (
                            symbol, name, longitude, box, path
                        )
                        try:
                            if witness_members(next_remaining):
                                return True
                        finally:
                            staged.pop(original_index, None)
                            leader_names.pop()
                            leaders.pop()
                            placed.pop()
                finally:
                    stream.close()
                return False

            return witness_members(candidate_items)

        def recurse_after_blob():
            nonlocal completions
            completions += 1
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT RECURSIVE BLOB "
                f"group={group_index + 1} completion={completions} "
                f"preplaced={'|'.join(leader_names)}",
                level=1, flush=True,
            )
            for remaining_group_index in next_groups:
                if not remaining_blob_has_witness(remaining_group_index):
                    diagnostic_print(
                        f"Planet Finder {mode}: ALIGNMENT BLOB FORWARD REJECT "
                        f"group={group_index + 1} completion={completions} "
                        f"blocked_group={remaining_group_index + 1}",
                        level=1, flush=True,
                    )
                    return False
            solved = solve_alignment_group(next_groups)
            if not solved:
                diagnostic_print(
                    f"Planet Finder {mode}: ALIGNMENT RECURSIVE DISCARD "
                    f"group={group_index + 1} completion={completions}",
                    level=1, flush=True,
                )
            return solved

        solved = solve_alignment_members(
            group_index, list(group_items), recurse_after_blob
        )
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT RECURSIVE EXIT "
            f"group={group_index + 1} solved={solved} completions={completions}",
            level=1, flush=True,
        )
        return solved

    forward_stats = {"checks": 0, "pruned": 0, "witnesses": 0, "by_body": {}}
    # Diagnostic only: blocker identities for forward candidate rejection.
    forward_blocker_names = {}
    # Diagnostic only: blocker identities inside Ceres forward viability.
    forward_ceres_blockers = {
        "overlap": {}, "existing-leader": {}, "leader-graze": {},
        "route-direct": {}, "route-escape": {}, "route-arc": {}, "route-final": {},
    }
    forward_ceres_route_other = {}
    # Diagnostic only: correlate the currently placed Mercury geometry with
    # Ceres forward-check success/failure. This answers whether backtracking is
    # exploring materially different Mercury placements or repeatedly
    # stranding Ceres with equivalent geometry.
    mercury_ceres_trials = {}
    # Diagnostic only: capture a compact trace for the first Mercury geometry
    # tested against Ceres. Candidate generation is widest-first, so this is
    # the geometry that should succeed before any narrowing is necessary.
    mercury_ceres_first_signature = [None]
    mercury_ceres_first_candidates = []
    # Diagnostic only: first Venus forward probe under a placed Mercury prefix.
    # Capture exact candidate rejection classes without changing viability.
    mercury_venus_first_signature = [None]
    mercury_venus_first_candidates = []
    # Bodies that actually make a forward check fail.  Without this, a prefix
    # whose every candidate is pruned before recursion leaves `deepest` at the
    # parent depth, causing the controller to blame/promote the parent instead
    # of the future body that is the real squeaky wheel.
    forward_blockers = {}
    # A future body can be the true squeaky wheel without ever reaching its
    # own DFS depth: forward checking may repeatedly prove it dead first.
    # After enough independent dead prefixes, hand that evidence to the outer
    # controller so the same generic promotion machinery can move it earlier.
    forward_blocker_promotion_threshold = max(
        1, int(os.environ.get("PLANET_FINDER_FORWARD_BLOCKER_PROMOTION", "25"))
    )
    forward_parent_effect = {"checks": 0, "raw": 0, "parent_box": 0, "parent_leader": 0, "other": 0}
    # Forward checking is only a pruning hint.  Bound raw look-ahead work so
    # a difficult body cannot monopolize the mode clock.  Hitting this cap is
    # UNKNOWN, never proof that the branch is dead.
    forward_probe_cap = max(
        1, int(os.environ.get("PLANET_FINDER_FORWARD_PROBE_CAP", "1000"))
    )
    PROBE_LIMITED = object()
    uranus_without_pluto_done = [False]

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

        def witness_for(item, boxes, paths, obstacles_now, collect_blockers=True):
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
                first_mercury_index = next(
                    (i for i, placed_name in enumerate(leader_names) if placed_name == "Mercury"),
                    None,
                ) if future_name in {"Ceres", "Venus"} else None
                first_mercury_signature = None
                if first_mercury_index is not None and first_mercury_index < len(boxes):
                    mb = boxes[first_mercury_index]
                    mp = paths[first_mercury_index]
                    first_mercury_signature = (
                        round(mb.x, 1), round(mb.y, 1), round(mb.w, 1), round(mb.h, 1),
                        tuple((round(px, 1), round(py, 1)) for px, py in mp),
                    )
                    if future_name == "Ceres" and mercury_ceres_first_signature[0] is None:
                        mercury_ceres_first_signature[0] = first_mercury_signature
                    if future_name == "Venus" and mercury_venus_first_signature[0] is None:
                        mercury_venus_first_signature[0] = first_mercury_signature
                trace_first = (
                    future_name == "Ceres"
                    and first_mercury_signature == mercury_ceres_first_signature[0]
                    and len(mercury_ceres_first_candidates) < 12
                )
                trace_venus = (
                    future_name == "Venus"
                    and first_mercury_signature == mercury_venus_first_signature[0]
                )
                overlap_hits = [i for i, other in enumerate(boxes) if boxes_overlap(future_box, other, 14)]
                if overlap_hits:
                    reasons["placed-overlap"] += 1
                    if collect_blockers:
                        buckets = forward_blocker_names.setdefault(future_name, {"placed-overlap": {}, "existing-leader": {}, "leader-graze": {}})
                        for i in overlap_hits:
                            blocker = leader_names[i] if i < len(leader_names) else f"placed_{i}"
                            counts = buckets["placed-overlap"]
                            counts[blocker] = counts.get(blocker, 0) + 1
                    if future_name == "Uranus" and leader_names and leader_names[-1] == "Pluto":
                        forward_parent_effect["raw"] += 1
                        if (len(boxes) - 1) in overlap_hits:
                            forward_parent_effect["parent_box"] += 1
                        else:
                            forward_parent_effect["other"] += 1
                    if future_name == "Ceres":
                        for i in overlap_hits:
                            blocker = leader_names[i] if i < len(leader_names) else f"placed_{i}"
                            counts = forward_ceres_blockers["overlap"]
                            counts[blocker] = counts.get(blocker, 0) + 1
                    if trace_first:
                        mercury_ceres_first_candidates.append(
                            f"box=({future_box.x:.1f},{future_box.y:.1f},{future_box.w:.1f},{future_box.h:.1f}) "
                            f"reject=overlap blockers={','.join(leader_names[i] if i < len(leader_names) else f'placed_{i}' for i in overlap_hits)}"
                        )
                    continue
                leader_hits = [
                    j for j, seg in enumerate(paths)
                    if any(segment_hits_box(seg[i], seg[i + 1], future_box, 10)
                           for i in range(len(seg) - 1))
                ]
                if leader_hits:
                    reasons["existing-leader"] += 1
                    if collect_blockers:
                        buckets = forward_blocker_names.setdefault(future_name, {"placed-overlap": {}, "existing-leader": {}, "leader-graze": {}})
                        for j in leader_hits:
                            blocker = leader_names[j] if j < len(leader_names) else f"leader_{j}"
                            counts = buckets["existing-leader"]
                            counts[blocker] = counts.get(blocker, 0) + 1
                    if future_name == "Uranus" and leader_names and leader_names[-1] == "Pluto":
                        forward_parent_effect["raw"] += 1
                        if (len(paths) - 1) in leader_hits:
                            forward_parent_effect["parent_leader"] += 1
                        else:
                            forward_parent_effect["other"] += 1
                    if future_name == "Ceres":
                        for j in leader_hits:
                            blocker = leader_names[j] if j < len(leader_names) else f"leader_{j}"
                            counts = forward_ceres_blockers["existing-leader"]
                            counts[blocker] = counts.get(blocker, 0) + 1
                    if trace_first:
                        mercury_ceres_first_candidates.append(
                            f"box=({future_box.x:.1f},{future_box.y:.1f},{future_box.w:.1f},{future_box.h:.1f}) "
                            f"reject=existing-leader blockers={','.join(leader_names[j] if j < len(leader_names) else f'leader_{j}' for j in leader_hits)}"
                        )
                    continue
                center = (future_box.x, future_box.y)
                forward_route_diag = {} if future_name == "Ceres" else None
                # Forward checking must test the same drawable leader
                # geometry as ordinary DFS.  Routing to the label center makes
                # the probe segment artificially longer and can create false
                # leader-graze/dead results for close conjunctions.
                path = route(
                    anchor,
                    center,
                    obstacles_now,
                    forward_route_diag,
                    allow_initial_escape_count=immutable_count,
                    prefix_cache=prefix_cache,
                    target_box=future_box,
                    existing_paths=paths,
                )
                if path is None:
                    reasons["route"] += 1
                    if future_name == "Ceres":
                        obstacle_names = reserved_names + list(leader_names)
                        for diag_key, bucket in (
                            ("direct_blocked_by", "route-direct"),
                            ("escape_blocked_by", "route-escape"),
                            ("arc_blocked_by", "route-arc"),
                            ("final_blocked_by", "route-final"),
                        ):
                            for obstacle_index, count in forward_route_diag.get(diag_key, {}).items():
                                blocker = obstacle_names[obstacle_index] if obstacle_index < len(obstacle_names) else f"obstacle_{obstacle_index}"
                                counts = forward_ceres_blockers[bucket]
                                counts[blocker] = counts.get(blocker, 0) + count
                        for diag_key in ("anchor_blocked", "target_approach"):
                            count = forward_route_diag.get(diag_key, 0)
                            if count:
                                forward_ceres_route_other[diag_key] = forward_ceres_route_other.get(diag_key, 0) + count
                    continue
                if leader_hits_zodiac_rim(path):
                    reasons["leader-rim"] += 1
                    continue
                if leaders_too_close(path, paths):
                    reasons["leader-graze"] += 1
                    if collect_blockers:
                        _, blocker_pair = minimum_leader_separation(path, paths)
                        if blocker_pair is not None:
                            j = blocker_pair[0]
                            blocker = leader_names[j] if j < len(leader_names) else f"leader_{j}"
                            buckets = forward_blocker_names.setdefault(future_name, {"placed-overlap": {}, "existing-leader": {}, "leader-graze": {}})
                            counts = buckets["leader-graze"]
                            counts[blocker] = counts.get(blocker, 0) + 1
                    if future_name == "Ceres":
                        _, blocker_pair = minimum_leader_separation(path, paths)
                        if blocker_pair is not None:
                            j = blocker_pair[0]
                            blocker = leader_names[j] if j < len(leader_names) else f"leader_{j}"
                            counts = forward_ceres_blockers["leader-graze"]
                            counts[blocker] = counts.get(blocker, 0) + 1
                    if trace_venus and len(mercury_venus_first_candidates) < 12:
                        min_dist, blocker_pair = minimum_leader_separation(path, paths)
                        blocker = "-"
                        segment_pair = "-/-"
                        anchor_sep = float("nan")
                        proposed_path = tuple(
                            (round(px, 1), round(py, 1)) for px, py in path
                        )
                        existing_path = ()
                        if blocker_pair is not None:
                            j = blocker_pair[0]
                            blocker = (
                                leader_names[j]
                                if j < len(leader_names)
                                else f"leader_{j}"
                            )
                            segment_pair = f"{blocker_pair[1]}/{blocker_pair[2]}"
                            if j < len(paths):
                                other = paths[j]
                                anchor_sep = math.hypot(
                                    path[0][0] - other[0][0],
                                    path[0][1] - other[0][1],
                                )
                                existing_path = tuple(
                                    (round(px, 1), round(py, 1))
                                    for px, py in other
                                )
                        mercury_venus_first_candidates.append(
                            f"box=({future_box.x:.1f},{future_box.y:.1f},"
                            f"{future_box.w:.1f},{future_box.h:.1f}) "
                            f"reject=leader-graze blocker={blocker} "
                            f"distance={min_dist:.3f} "
                            f"clearance={LEADER_TO_LEADER_CLEARANCE:.3f} "
                            f"segments={segment_pair} "
                            f"anchor-separation={anchor_sep:.3f} "
                            f"close-anchors="
                            f"{anchor_sep < LEADER_TO_LEADER_CLEARANCE} "
                            f"venus-path={proposed_path} "
                            f"blocker-path={existing_path}"
                        )
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

        # Cheap prefix gate: independently test every remaining DFS body
        # against the CURRENT placed prefix. One viable witness per body is
        # enough to preserve the prefix; zero proves this prefix is dead.
        #
        # This is deliberately not Child -> Grandchild combinatorial look-ahead:
        # future bodies are never staged here and are not tested against one
        # another. Ordinary DFS still owns all multi-body compatibility and
        # backtracking decisions.
        if next_depth >= len(order):
            return True
        future_items = [
            (future_depth, order[future_depth])
            for future_depth in range(next_depth, len(order))
            if order[future_depth][0] not in staged
        ]
        # Forward witnesses are independent necessary-condition probes against
        # the same current prefix, so their evaluation order cannot change
        # correctness.  Probe the historically hardest future body first.
        # Venus is the dominant W01 failure: discovering a dead Venus prefix
        # immediately avoids spending the shared look-ahead budget on easier
        # bodies before repeating the expensive Venus route search.
        forward_priority = {"Venus": 0}
        future_items.sort(
            key=lambda row: (
                forward_priority.get(row[1][1][1], 1),
                row[0],
            )
        )
        for future_depth, item in future_items:
            _, (_, future_name, _) = item
            if future_name == "Uranus" and leader_names and leader_names[-1] == "Pluto":
                forward_parent_effect["checks"] += 1
            future_box, future_path, witness_raw, witness_reasons = witness_for(
                item, placed, leaders, obstacles
            )
            if (
                future_name == "Uranus"
                and leader_names and leader_names[-1] == "Pluto"
                and not uranus_without_pluto_done[0]
            ):
                uranus_without_pluto_done[0] = True
                cf_box, _, cf_raw, cf_reasons = witness_for(
                    item, placed[:-1], leaders[:-1], [*reserved, *placed[:-1]],
                    collect_blockers=False,
                )
                cf_state = "PROBE-LIMITED" if cf_box is PROBE_LIMITED else ("WITNESS" if cf_box is not None else "DEAD")
                diagnostic_print(
                    f"Planet Finder {mode}: URANUS-WITHOUT-PLUTO {cf_state} raw={cf_raw:,} "
                    f"reasons={cf_reasons}",
                    level=1, flush=True,
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
            if future_name == "Venus" and mercury_venus_first_candidates and mercury_venus_first_signature[0] is not None:
                diagnostic_print(
                    f"Planet Finder {mode}: MERCURY->VENUS FIRST-PROBE "
                    f"mercury={mercury_venus_first_signature[0]} raw={witness_raw:,} witness={witness} "
                    f"reasons={witness_reasons} candidates={mercury_venus_first_candidates}",
                    level=1, flush=True,
                )
                mercury_venus_first_candidates.clear()
                mercury_venus_first_signature[0] = None
            body_stat = forward_stats["by_body"].setdefault(
                future_name, {"checks": 0, "witnesses": 0, "dead": 0, "raw": 0,
                               "reasons": {"placed-overlap": 0, "existing-leader": 0,
                                          "route": 0, "leader-rim": 0, "leader-graze": 0}}
            )
            body_stat["checks"] += 1
            body_stat["raw"] += witness_raw
            for reason, count in witness_reasons.items():
                body_stat["reasons"][reason] += count
            if future_name == "Ceres":
                mercury_index = next(
                    (i for i, placed_name in enumerate(leader_names) if placed_name == "Mercury"),
                    None,
                )
                if mercury_index is not None and mercury_index < len(placed):
                    mercury_box = placed[mercury_index]
                    mercury_path = leaders[mercury_index]
                    mercury_signature = (
                        round(mercury_box.x, 1), round(mercury_box.y, 1),
                        round(mercury_box.w, 1), round(mercury_box.h, 1),
                        tuple((round(px, 1), round(py, 1)) for px, py in mercury_path),
                    )
                    trial = mercury_ceres_trials.setdefault(
                        mercury_signature,
                        {
                            "checks": 0, "witnesses": 0, "dead": 0, "raw": 0,
                            "reasons": {
                                "placed-overlap": 0, "existing-leader": 0,
                                "route": 0, "leader-rim": 0, "leader-graze": 0,
                            },
                        },
                    )
                    trial["checks"] += 1
                    trial["raw"] += witness_raw
                    trial["witnesses"] += int(witness)
                    trial["dead"] += int(not witness)
                    for reason, count in witness_reasons.items():
                        trial["reasons"][reason] += count

            if witness:
                body_stat["witnesses"] += 1
                forward_stats["witnesses"] += 1
            else:
                body_stat["dead"] += 1
                forward_stats["pruned"] += 1
                forward_blockers[future_name] = forward_blockers.get(future_name, 0) + 1
                if forward_blockers[future_name] >= forward_blocker_promotion_threshold:
                    diagnostic_print(
                        f"Planet Finder {mode}: FORWARD SQUEAKY-WHEEL "
                        f"body={future_name} dead-prefixes={forward_blockers[future_name]:,}/"
                        f"{forward_blocker_promotion_threshold:,}; requesting promotion",
                        flush=True,
                    )
                    raise ForwardBlockerRepeated(
                        future_name, forward_blockers[future_name]
                    )
                if next_depth == 1 and order[0][1][1] == "Sun":
                    diagnostic_print(
                        f"Planet Finder {mode}: SUN-PREFIX DEAD-GATE "
                        f"sun-check={forward_stats['checks']:,} "
                        f"future-body={future_name} raw={witness_raw:,} "
                        f"prefix-obstacles={len(obstacles):,}",
                        level=3,
                        flush=True,
                    )
                if leader_names:
                    # Diagnostic only.  Being dead after removing the immediate
                    # parent proves only that THIS prefix is dead; earlier
                    # ancestors may still have sibling placements that free the
                    # future body.  Never promote this observation into a
                    # whole-order exception -- ordinary DFS must unwind and try
                    # those siblings.
                    parentless_box, _, _, _ = witness_for(
                        item, placed[:-1], leaders[:-1], [*reserved, *placed[:-1]],
                        collect_blockers=False,
                    )
                    if parentless_box is None:
                        diagnostic_print(
                            f"Planet Finder {mode}: FORWARD PREFIX DEAD body={future_name}; "
                            f"still dead without immediate parent={leader_names[-1]}; "
                            "returning False for normal DFS backtracking",
                            level=1, flush=True,
                        )
                return False

        if forward_parent_effect["checks"] and forward_parent_effect["checks"] % 100 == 0:
            diagnostic_print(
                f"Planet Finder {mode}: URANUS-PARENT-SUMMARY checks={forward_parent_effect['checks']:,} "
                f"raw={forward_parent_effect['raw']:,} Pluto-box={forward_parent_effect['parent_box']:,} "
                f"Pluto-leader={forward_parent_effect['parent_leader']:,} other={forward_parent_effect['other']:,}",
                level=1, flush=True,
            )

        # Child -> Grandchild look-ahead intentionally disabled.
        # Individual future-body witness checks remain active above.
        # Ordinary DFS now owns all multi-body compatibility decisions.

        return True

    def search(depth):
        """Run one DFS frame with its ordering mutation scoped to that frame.

        Fail-first selection below temporarily reorders the shared order list.
        Every recursive frame must restore the ordering it inherited when it
        returns, otherwise a child's MRV choice leaks into its parent's next
        sibling and the search revisits a drifting permutation space.
        """
        inherited_order = list(order)
        try:
            return search_frame(depth)
        finally:
            order[:] = inherited_order

    def search_frame(depth):
        """Recursive DFS body: each call owns exactly one body depth.

        Geometry rejects bad proposals before they enter this function.
        Returning from a child is the only backtracking mechanism.
        """
        nonlocal nodes, deepest, candidates, backtracks, current_body
        nonlocal terminal_validation_checks, terminal_validation_rejections
        nonlocal terminal_validation_sun_leaders, refinement_timed_out

        now = time.monotonic()
        if refinement_deadline is not None and now >= refinement_deadline:
            refinement_timed_out = True
            diagnostic_print(
                f"Planet Finder {mode}: DFS REFINEMENT DEADLINE order={order_index} "
                f"depth={depth}/{len(order)} body={current_body}; returning to controller",
                flush=True,
            )
            return False

        nodes += 1
        deepest = max(deepest, depth)
        depth_visits[depth] = depth_visits.get(depth, 0) + 1

        # Diagnostic-only W17 Venus depth trace.  At every committed DFS
        # prefix, exhaustively count Venus candidates against exactly that
        # prefix.  This exposes the first positive -> zero transition and the
        # newly committed body that caused it.  The trace is opt-in and never
        # participates in normal search decisions.
        if os.environ.get("PLANET_FINDER_VENUS_DEPTH_TRACE") == "1":
            venus_item = next(
                (
                    item for future_depth, item in enumerate(order)
                    if future_depth >= depth
                    and item[0] not in staged
                    and item[1][1] == "Venus"
                ),
                None,
            )
            if venus_item is not None:
                before_stats = dict(diagnostic_stats.get((depth, "Venus"), {}))
                venus_count = 0
                venus_probe = viable_candidates(
                    venus_item, depth, consume_body_budget=False
                )
                try:
                    for _ in venus_probe:
                        venus_count += 1
                finally:
                    venus_probe.close()
                after_stats = diagnostic_stats.get((depth, "Venus"), {})
                keys = (
                    "generated", "viable", "immutable_reserved", "immutable_rim",
                    "overlap", "leader_existing", "route", "leader_rim",
                    "leader_graze",
                )
                delta = {
                    key: after_stats.get(key, 0) - before_stats.get(key, 0)
                    for key in keys
                }
                parent = leader_names[-1] if leader_names else "ROOT"
                diagnostic_print(
                    f"Planet Finder {mode}: VENUS DEPTH TRACE "
                    f"depth={depth}/{len(order)} parent={parent} "
                    f"prefix={'|'.join(leader_names) or 'ROOT'} "
                    f"viable={venus_count} generated={delta['generated']} "
                    f"rejects[reserved={delta['immutable_reserved']},"
                    f"rim={delta['immutable_rim']},overlap={delta['overlap']},"
                    f"existing-leader={delta['leader_existing']},"
                    f"route={delta['route']},leader-rim={delta['leader_rim']},"
                    f"leader-graze={delta['leader_graze']}]",
                    level=1, flush=True,
                )
                if venus_count == 0:
                    raise RuntimeError(
                        f"VENUS_DEPTH_TRACE_ZERO depth={depth} parent={parent} "
                        f"prefix={'|'.join(leader_names) or 'ROOT'}"
                    )

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

        # Alignment/conjunction members may already be staged by the coordinated
        # preplacement layer. They are complete DFS choices, not ordinary bodies
        # to place a second time. Advance past them while preserving their staged
        # geometry so backtracking remains owned by the alignment layer.
        if original_index in staged:
            return search(depth + 1)

        # Fail-first / squeaky-wheel selection belongs INSIDE the recursion.
        # At this prefix, probe every still-unplaced body and recurse on the one
        # with the fewest currently viable placements.  The probe is bounded:
        # once a body has enough witnesses to lose the fail-first contest, exact
        # counting is unnecessary.  Probes never consume the body's DFS cap.
        fixed_prefix = max(
            0, int(os.environ.get("PLANET_FINDER_DFS_FIXED_PREFIX", "0"))
        )
        mrv_probe_limit = max(
            1, int(os.environ.get("PLANET_FINDER_MRV_PROBE_LIMIT", "25"))
        )
        if depth >= fixed_prefix:
            ranked = []
            for candidate_index in range(depth, len(order)):
                candidate_item = order[candidate_index]
                if candidate_item[0] in staged:
                    continue
                probe = viable_candidates(
                    candidate_item, depth, consume_body_budget=False
                )
                viable_count = 0
                try:
                    for _ in probe:
                        viable_count += 1
                        if viable_count >= mrv_probe_limit:
                            break
                finally:
                    probe.close()
                ranked.append((viable_count, candidate_index))
                if viable_count == 0:
                    break

            if ranked:
                viable_count, chosen_index = min(
                    ranked, key=lambda row: (row[0], row[1])
                )
                if chosen_index != depth:
                    chosen_name = order[chosen_index][1][1]
                    displaced_name = order[depth][1][1]
                    chosen_item = order.pop(chosen_index)
                    order.insert(depth, chosen_item)
                    diagnostic_print(
                        f"Planet Finder {mode}: DFS SQUEAKY-WHEEL "
                        f"depth={depth}/{len(order)} choose={chosen_name} "
                        f"viable<={viable_count} displaced={displaced_name}",
                        level=1, flush=True,
                    )
                item = order[depth]
                original_index, (symbol, name, longitude) = item

        current_body = name
        generated_here = False
        forensic = dfs_forensics.setdefault(depth, {
            "admitted": 0, "forward_pass": 0, "forward_fail": 0,
            "child_calls": 0, "child_success": 0, "backtracks": 0,
            "subtree_time": 0.0, "max_child_depth": depth,
        })

        for box, path in viable_candidates(item, depth):
            generated_here = True
            candidates += 1
            forensic["admitted"] += 1
            if os.environ.get("PLANET_FINDER_SKIP_ALIGNMENT_PREPLANNER", "0") == "1":
                admitted_here = forensic["admitted"]
                if admitted_here <= 3 or admitted_here in (10, 25, 50, 100, 200, 500, 1000, 2000):
                    diagnostic_print(
                        f"Planet Finder {mode}: FORENSIC DFS ADMIT "
                        f"depth={depth}/{len(order)} body={name} "
                        f"body_candidate={admitted_here:,} global_candidate={candidates:,} "
                        f"box=({box.x:.2f},{box.y:.2f},{box.w:.2f},{box.h:.2f}) "
                        f"path={tuple((round(px,2), round(py,2)) for px,py in path)}",
                        flush=True,
                    )
            placed.append(box)
            leaders.append(path)
            leader_names.append(name)
            staged[original_index] = (symbol, name, longitude, box, path)

            child_deepest_before = deepest
            child_nodes_before = nodes
            child_backtracks_before = backtracks
            branch_started = time.monotonic()
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
                forward_ok = forward_check(depth + 1)
                if forward_ok:
                    forensic["forward_pass"] += 1
                    forensic["child_calls"] += 1
                    if os.environ.get("PLANET_FINDER_SKIP_ALIGNMENT_PREPLANNER", "0") == "1" and (
                        forensic["forward_pass"] <= 3 or forensic["forward_pass"] in (10, 25, 50, 100, 200)
                    ):
                        diagnostic_print(
                            f"Planet Finder {mode}: FORENSIC FORWARD PASS "
                            f"depth={depth}/{len(order)} body={name} "
                            f"passes={forensic['forward_pass']:,} fails={forensic['forward_fail']:,}",
                            flush=True,
                        )
                    child_ok = search(depth + 1)
                    forensic["max_child_depth"] = max(forensic["max_child_depth"], deepest)
                    if child_ok:
                        forensic["child_success"] += 1
                        return True
                else:
                    forensic["forward_fail"] += 1
                    if os.environ.get("PLANET_FINDER_SKIP_ALIGNMENT_PREPLANNER", "0") == "1" and (
                        forensic["forward_fail"] <= 3 or forensic["forward_fail"] in (10, 25, 50, 100, 200, 500, 1000)
                    ):
                        diagnostic_print(
                            f"Planet Finder {mode}: FORENSIC FORWARD FAIL "
                            f"depth={depth}/{len(order)} body={name} "
                            f"passes={forensic['forward_pass']:,} fails={forensic['forward_fail']:,} "
                            f"deepest={deepest}/{len(order)}",
                            flush=True,
                        )
            finally:
                forensic["subtree_time"] += time.monotonic() - branch_started
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
            forensic["backtracks"] += 1
            forensic["max_child_depth"] = max(forensic["max_child_depth"], deepest)
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
        # Diagnostic-only escape hatch: bypass the coordinated alignment
        # layer so this forensic exercises ordinary recursive DFS/backtracking.
        if os.environ.get("PLANET_FINDER_SKIP_ALIGNMENT_PREPLANNER", "0") == "1":
            order_names = " > ".join(item[1][1] for item in order)
            diagnostic_print(
                f"Planet Finder {mode}: FORENSIC ORDINARY-DFS BYPASS "
                f"sequence={order_names} staged={len(staged)} "
                f"placed={len(placed)} leaders={len(leaders)}",
                flush=True,
            )
            return search(0)

        # Conjunctions have no placement path of their own.  Every body enters
        # the ordinary coordinated alignment planner; conjunction metadata is
        # consulted only by downstream backtracking to keep a conjunction
        # atomic when it must be reconsidered.
        phase_started = time.monotonic()
        before = predfs_rejection_snapshot()
        diagnostic_print(
            f"Planet Finder {mode}: PRE-DFS TIMING alignment-plan START",
            level=1, flush=True,
        )
        # Plan the crowded layer as a whole.  The planner now reserves wide
        # tangential slots for all members before any one member is committed.
        alignment_preplacement = plan_alignment_layer()
        if alignment_preplacement is None and alignment_group_items:
            check_deadline()
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT SPATIAL STAGGER RETRY "
                "planning labels and routes before recursive fallback",
                level=1, flush=True,
            )
            alignment_preplacement = plan_alignment_layer(stagger=True)
        diagnostic_print(
            f"Planet Finder {mode}: PRE-DFS TIMING alignment-plan END "
            f"elapsed={time.monotonic() - phase_started:.3f}s "
            f"result={'planned' if alignment_preplacement else 'none'}",
            level=1, flush=True,
        )
        report_predfs_phase("alignment-plan", before)

        phase_started = time.monotonic()
        before = predfs_rejection_snapshot()
        stage_alignment_preplacement(alignment_preplacement)
        diagnostic_print(
            f"Planet Finder {mode}: PRE-DFS TIMING alignment-stage END "
            f"elapsed={time.monotonic() - phase_started:.3f}s "
            f"staged={len(staged)}",
            level=1, flush=True,
        )
        report_predfs_phase("alignment-stage", before)

        phase_started = time.monotonic()
        before = predfs_rejection_snapshot()
        diagnostic_print(
            f"Planet Finder {mode}: PRE-DFS TIMING alignment-fallback START",
            level=1, flush=True,
        )
        fallback_result = _search_alignment_fallback(
            alignment_preplacement, alignment_group_items, placed, leaders,
            leader_names, staged, search, solve_alignment_group,
        )
        diagnostic_print(
            f"Planet Finder {mode}: PRE-DFS TIMING alignment-fallback END "
            f"elapsed={time.monotonic() - phase_started:.3f}s result={fallback_result}",
            level=1, flush=True,
        )
        probe_total = sum(alignment_probe_signatures.values())
        probe_unique = len(alignment_probe_signatures)
        probe_repeated = probe_total - probe_unique
        top_repeats = sorted(
            (
                (count, key[0] + 1, key[1], key[2])
                for key, count in alignment_probe_signatures.items()
                if count > 1
            ),
            reverse=True,
        )[:12]
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT STATE REPETITION "
            f"evaluations={probe_total:,} unique={probe_unique:,} repeated={probe_repeated:,} "
            f"repeat_pct={(100.0 * probe_repeated / probe_total if probe_total else 0.0):.1f}% "
            f"top={top_repeats}",
            level=1, flush=True,
        )
        report_predfs_phase("alignment-fallback", before)
        return fallback_result

    try:
        solved = search_coordinated_geometry()
        if (refinement_deadline is not None and time.monotonic() >= refinement_deadline
                and not solved):
            refinement_timed_out = True
        exhausted = not solved and not refinement_timed_out
    except SearchDeadlineExhausted:
        refinement_timed_out = True
        solved = False
        exhausted = False
    except ForwardBlockerExhausted as exc:
        dump_diagnostics(f"early forward blocker body={exc.name}")
        return SearchOutcome("EXHAUSTED", [], [], exc.name, {
            "source": "forward-check-parent-independent",
        })
    except ForwardBlockerRepeated as exc:
        dump_diagnostics(
            f"repeated forward blocker body={exc.name} dead-prefixes={exc.count}"
        )
        return SearchOutcome("CAPPED", [], [], exc.name, {
            "source": "forward-check-repeated",
            "dead_prefixes": exc.count,
            "threshold": forward_blocker_promotion_threshold,
        })
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

    if refinement_timed_out:
        probe_total = sum(alignment_probe_signatures.values())
        probe_unique = len(alignment_probe_signatures)
        probe_repeated = probe_total - probe_unique
        top_repeats = sorted(
            (
                (count, key[0] + 1, key[1], key[2])
                for key, count in alignment_probe_signatures.items()
                if count > 1
            ),
            reverse=True,
        )[:12]
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT STATE REPETITION DEADLINE "
            f"evaluations={probe_total:,} unique={probe_unique:,} repeated={probe_repeated:,} "
            f"repeat_pct={(100.0 * probe_repeated / probe_total if probe_total else 0.0):.1f}% "
            f"top={top_repeats}",
            level=1, flush=True,
        )
        report_alignment_layer_shape()
        report_alignment_phase_profile()
        report_alignment_route_forensics()
        dump_diagnostics("refinement deadline reached before search completed")
    elif exhausted:
        dump_diagnostics("search exhausted without a complete solution")

    report_alignment_phase_profile()
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
        # Report rejection evidence from the mechanism that actually selected
        # the blocker. A body killed by forward checking may never be entered
        # by DFS, so its ordinary diagnostic_stats are legitimately all zero.
        # In that case the forward witness reasons are the authoritative
        # explanation for why the body had no contestant.
        if blocker in forward_blockers:
            fs = forward_stats["by_body"].get(blocker, {})
            reasons = fs.get("reasons", {})
            blocker_stats = {
                "source": "forward-check",
                "checks": fs.get("checks", 0),
                "witnesses": fs.get("witnesses", 0),
                "dead": fs.get("dead", 0),
                "raw": fs.get("raw", 0),
                "placed_overlap": reasons.get("placed-overlap", 0),
                "existing_leader": reasons.get("existing-leader", 0),
                "route": reasons.get("route", 0),
                "leader_rim": reasons.get("leader-rim", 0),
                "leader_graze": reasons.get("leader-graze", 0),
            }
        else:
            blocker_depth = next(
                (depth for depth, item in enumerate(order) if item[1][1] == blocker),
                None,
            )
            if blocker_depth is not None:
                ds = diagnostic_stats.get((blocker_depth, blocker), {})
                if blocker == "Uranus":
                    def top_blockers(key):
                        return sorted(
                            ds.get(key, {}).items(),
                            key=lambda pair: (-pair[1], pair[0]),
                        )[:8]
                    diagnostic_print(
                        f"Planet Finder {mode}: URANUS PREPLACED BLOCKERS "
                        f"labels={top_blockers('overlap_by_label')} "
                        f"leaders={top_blockers('existing_leader_by_name')} "
                        f"leader-graze={top_blockers('leader_graze_by_name')}",
                        level=1, flush=True,
                    )
                blocker_stats = {
                    "source": "dfs",
                    "immutable_reserved": ds.get("immutable_reserved", 0),
                    "immutable_rim": ds.get("immutable_rim", 0),
                    "placed_overlap": ds.get("overlap", 0),
                    "existing_leader": ds.get("leader_existing", 0),
                    "route": ds.get("route", 0),
                    "leader_rim": ds.get("leader_rim", 0),
                    "leader_graze": ds.get("leader_graze", 0),
                }
    if (exhausted or refinement_timed_out) and forward_stats["by_body"]:
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
            blocker_buckets = forward_blocker_names.get(body, {})
            if blocker_buckets:
                def ranked_forward_blockers(kind):
                    return ",".join(
                        f"{name}={count:,}"
                        for name, count in sorted(
                            blocker_buckets.get(kind, {}).items(),
                            key=lambda item: (-item[1], item[0]),
                        )
                    ) or "-"
                diagnostic_print(
                    f"Planet Finder {mode}: FORWARD BODY BLOCKERS body={body} "
                    f"placed-overlap=[{ranked_forward_blockers('placed-overlap')}] "
                    f"existing-leader=[{ranked_forward_blockers('existing-leader')}] "
                    f"leader-graze=[{ranked_forward_blockers('leader-graze')}]",
                    flush=True,
                )

    if exhausted and mercury_ceres_trials:
        ranked_trials = sorted(
            mercury_ceres_trials.items(),
            key=lambda item: (-item[1]["checks"], item[0]),
        )
        distinct = len(ranked_trials)
        successful = sum(1 for _, row in ranked_trials if row["witnesses"])
        total_checks = sum(row["checks"] for _, row in ranked_trials)
        total_dead = sum(row["dead"] for _, row in ranked_trials)
        samples = "; ".join(
            f"box={sig[:4]} path={sig[4]} checks={row['checks']} "
            f"witnesses={row['witnesses']} dead={row['dead']} raw={row['raw']}"
            for sig, row in ranked_trials[:12]
        )
        # The candidate lattice is deliberately widest-first.  The first
        # distinct Mercury geometry observed is therefore the critical
        # forensic case: it should leave Ceres a witness if the geometry
        # implementation is behaving as designed.
        widest_sig, widest_row = next(iter(mercury_ceres_trials.items()))
        widest_reasons = widest_row["reasons"]
        if mercury_ceres_first_candidates:
            diagnostic_print(
                f"Planet Finder {mode}: MERCURY->CERES WIDEST CANDIDATES "
                + " ; ".join(mercury_ceres_first_candidates),
                flush=True,
            )
        diagnostic_print(
            f"Planet Finder {mode}: MERCURY->CERES WIDEST-FIRST "
            f"box={widest_sig[:4]} path={widest_sig[4]} "
            f"checks={widest_row['checks']} witnesses={widest_row['witnesses']} "
            f"dead={widest_row['dead']} raw={widest_row['raw']} "
            f"reasons[placed-overlap={widest_reasons['placed-overlap']},"
            f"existing-leader={widest_reasons['existing-leader']},"
            f"route={widest_reasons['route']},"
            f"leader-rim={widest_reasons['leader-rim']},"
            f"leader-graze={widest_reasons['leader-graze']}]",
            flush=True,
        )
        diagnostic_print(
            f"Planet Finder {mode}: MERCURY->CERES GEOMETRY "
            f"distinct={distinct} checks={total_checks} dead={total_dead} "
            f"ceres-positive={successful} samples={samples}",
            flush=True,
        )

    if exhausted and forward_ceres_blockers:
        for kind, counts in forward_ceres_blockers.items():
            top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:12]
            diagnostic_print(
                f"Planet Finder {mode}: FORWARD CERES BLOCKERS kind={kind} "
                + (" ".join(f"{name}={count:,}" for name, count in top) if top else "none"),
                flush=True,
            )
        diagnostic_print(
            f"Planet Finder {mode}: FORWARD CERES ROUTE-OTHER "
            + (" ".join(f"{name}={count:,}" for name, count in sorted(forward_ceres_route_other.items()))
               if forward_ceres_route_other else "none"),
            flush=True,
        )

    return SearchOutcome(
        ("SOLVED" if len(solutions) >= target_solutions
         else "DEADLINE" if refinement_timed_out else "EXHAUSTED"),
        solutions,
        contest_keys,
        blocker,
        blocker_stats,
    )
