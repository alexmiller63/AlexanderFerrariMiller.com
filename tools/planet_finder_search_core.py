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
    legal_candidate_positions, route,
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

    # This object contains limits only. It deliberately contains no clock
    # state: every notation mode starts its own clock inside layout().
    return {
        "max_node_candidates": max_node_candidates,
        "max_seconds": max_seconds,
    }


def _solve_order(mode: str, bodies, order, budget, target_solutions=5, order_index=1, total_orders=None, context_label=None, displacement_scale=2.0, body_attempts=None, refinement_deadline=None):
    """Solve one fixed body ordering with recursive depth-first search.

    The ordering is fixed for this pass. Each recursive call owns one body
    depth; returning from a child restores the parent placement and tries the
    
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
        anchor = xy(longitude, RI - 5)
        # This generator is created for one fixed DFS prefix. The placed
        # obstacles therefore remain stable for its lifetime, so anchor-side
        # routing work can be safely reused across all candidate labels.
        route_prefix_cache = {}
        body_candidates = 0
        raw_positions = 0
        


    