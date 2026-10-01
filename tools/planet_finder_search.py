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


from planet_finder_search_core import (
    SearchOutcome,
    DepthNodeBudgetExhausted,
    diagnostic_print,
    new_search_budget,
    _solve_order,
)

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

    lambda_sorted = sorted(indexed, key=lambda item: item[1][2] % 360.0)
    gaps = []
    for i, item in enumerate(lambda_sorted):
        current_lambda = item[1][2] % 360.0
        next_lambda = lambda_sorted[(i + 1) % len(lambda_sorted)][1][2] % 360.0
        gap = (next_lambda - current_lambda) % 360.0
        gaps.append(gap)
    seam_after = max(range(len(gaps)), key=gaps.__getitem__)
    indexed = lambda_sorted[seam_after + 1:] + lambda_sorted[:seam_after + 1]

    conjunction_names = {
        item[1]
        for group in conjunction_groups(bodies)
        for item in group
    }
    indexed = [item for item in indexed if item[1][1] not in conjunction_names]
    if conjunction_names:
        diagnostic_print(
            f"Planet Finder {mode}: FIXED CONJUNCTIONS "
            + " > ".join(item[1] for group in conjunction_groups(bodies) for item in group)
            + "; remaining after conjunctions=" + str(len(indexed)), flush=True,
        )

    alignment_names = {
        item[1]
        for group in alignment_groups(bodies)
        for item in group
    }
    indexed = [item for item in indexed if item[1][1] not in alignment_names]
    if alignment_names:
        diagnostic_print(
            f"Planet Finder {mode}: FIXED ALIGNMENTS "
            + " | ".join(" > ".join(item[1] for item in group) for group in alignment_groups(bodies))
            + "; recursive bodies=" + str(len(indexed)), flush=True,
        )

    closest_pair = None
    for i, left in enumerate(lambda_sorted):
        right = lambda_sorted[(i + 1) % len(lambda_sorted)]
        left_name = left[1][1]
        right_name = right[1][1]
        left_lambda = left[1][2] % 360.0
        right_lambda = right[1][2] % 360.0
        separation = (right_lambda - left_lambda) % 360.0
        if closest_pair is None or separation < closest_pair[0]:
            closest_pair = (separation, left_name, right_name, left_lambda, right_lambda)
    if closest_pair is not None:
        separation, left_name, right_name, left_lambda, right_lambda = closest_pair
        diagnostic_print(
            f"Planet Finder {mode}: CLOSEST ECLIPTIC PAIR {left_name} lambda={left_lambda:.3f} deg; "
            f"{right_name} lambda={right_lambda:.3f} deg; separation={separation:.3f} deg", flush=True,
        )

    if target_solutions is None:
        target_solutions = max(1, int(os.environ.get("PLANET_FINDER_CANDIDATES", str(DEFAULT_CANDIDATE_LAYOUTS))))
    if budget is None:
        budget = new_search_budget()
    budget = dict(budget)
    budget["started"] = time.monotonic()
    # One absolute wall clock owns the entire notation-mode search.  Do not
    # reset or multiply it for retries, promotions, refinements, or DFS calls.
    hard_wall_seconds = budget["max_seconds"]
    mode_deadline = budget["started"] + hard_wall_seconds
    diagnostic_print(
        f"Planet Finder {mode}: MODE CLOCK STARTED: hard-limit={hard_wall_seconds:.1f}s",
        flush=True,
    )

    order = indexed
    all_solutions = []
    contest_keys = []
    order_index = 0
    attempted_orders = set()
    body_attempts = {name: 0 for _, (_, name, _) in indexed}
    search_history = []
    state = "SEARCH_ORDER"
    promote_body = None

    def terminal_search(reason):
        final_sequence = " > ".join(item[1][1] for item in order)
        diagnostic_print(
            f"Planet Finder {mode}: TERMINAL SEARCH DIAGNOSTIC reason={reason} "
            f"attempts={len(search_history)} final-sequence={final_sequence}", flush=True,
        )
        raise RuntimeError(
            f"Planet Finder {mode}: canonical candidate lattice exhausted; {reason}; "
            "see TERMINAL SEARCH DIAGNOSTIC above"
        )

    def next_promotion_order(current_order, body_name):
        body_index = next((i for i, item in enumerate(current_order) if item[1][1] == body_name), None)
        if body_index is None:
            return "MISSING", None
        if body_index == 0:
            return "AT_FRONT", None
        candidate = list(current_order)
        candidate[body_index - 1], candidate[body_index] = candidate[body_index], candidate[body_index - 1]
        names = tuple(item[1][1] for item in candidate)
        if names in attempted_orders:
            return "CYCLE", candidate
        return "PROMOTE", candidate

    while state != "SCORE":
        now = time.monotonic()
        if now - budget["started"] >= hard_wall_seconds:
            raise RuntimeError(
                f"Planet Finder {mode} emergency wall-clock fuse exhausted "
                f"(limit {hard_wall_seconds:.1f}s)"
            )

        if state == "PROMOTE":
            transition, promoted_order = next_promotion_order(order, promote_body)
            if transition == "AT_FRONT":
                terminal_search(f"blocker {promote_body} already promoted to position 0")
            elif transition == "PROMOTE":
                promoted_names = tuple(item[1][1] for item in promoted_order)
                order = promoted_order
                body_attempts[promote_body] = 0
                diagnostic_print(
                    f"Planet Finder {mode}: PROMOTE body={promote_body}; moved left one lambda neighbor; "
                    "restarting sequence=" + " > ".join(promoted_names), flush=True,
                )
                state = "SEARCH_ORDER"
            elif transition == "CYCLE":
                terminal_search(f"ordering cycle while promoting {promote_body}")
            else:
                raise RuntimeError(
                    f"Planet Finder {mode}: controller invariant violated: blocker {promote_body!r} is absent from the recursive search order"
                )
            continue

        if state != "SEARCH_ORDER":
            raise RuntimeError(f"Planet Finder {mode}: invalid controller state {state}")

        order_names = tuple(item[1][1] for item in order)
        if order_names in attempted_orders:
            terminal_search("repeated ordering in single canonical lattice")
        attempted_orders.add(order_names)
        order_index += 1
        diagnostic_print(
            f"Planet Finder {mode}: squeaky-wheel lazy DFS {context_label + ' ' if context_label else ''}"
            f"order={order_index} target={target_solutions} max-node-candidates={budget['max_node_candidates']:,} "
            f"candidate-lattice=+/-2.00,...,+/-0.25,0 label-lengths sequence=" + " > ".join(order_names), flush=True,
        )

        try:
            outcome = _solve_order(
                mode, bodies, order, budget, target_solutions=target_solutions,
                order_index=order_index, total_orders=None, context_label=context_label,
                displacement_scale=0.25, body_attempts=body_attempts,
                refinement_deadline=mode_deadline,
            )
        except DepthNodeBudgetExhausted as exc:
            outcome = SearchOutcome("CAPPED", [], [], exc.name, None)

        diagnostic_print(
            f"Planet Finder {mode}: OUTCOME TRACE attempt={order_index} kind={outcome.kind} "
            f"blocker={outcome.blocker} rejection_stats={outcome.rejection_stats!r}", flush=True,
        )

        if outcome.kind == "SOLVED":
            all_solutions = outcome.solutions
            contest_keys = outcome.contest_keys
            state = "SCORE"
            continue
        if outcome.kind == "INCONCLUSIVE":
            raise RuntimeError(
                f"Planet Finder {mode}: bounded search inconclusive; no valid {target_solutions}-contestant contest was established"
            )
        if outcome.kind not in ("CAPPED", "EXHAUSTED") or not outcome.blocker:
            raise RuntimeError(f"Planet Finder {mode}: invalid search outcome kind={outcome.kind} blocker={outcome.blocker}")

        all_solutions = outcome.solutions
        contest_keys = outcome.contest_keys
        promote_body = outcome.blocker
        search_history.append({"kind": outcome.kind, "blocker": promote_body, "order": order_names})
        diagnostic_print(
            f"Planet Finder {mode}: SEARCH OUTCOME {outcome.kind} body={promote_body} "
            f"contestants={len(all_solutions)}/{target_solutions}", flush=True,
        )
        state = "PROMOTE"

    if not all_solutions:
        raise RuntimeError(f"No collision-free Planet Finder layout found in {mode} mode")

    def score(result):
        total_length = 0.0
        elbows = 0
        radial_error = 0.0
        tangential_error = 0.0
        for _, _, longitude, box, path in result:
            total_length += sum(math.hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(path, path[1:]))
            elbows += max(0, len(path) - 2)
            natural = xy(longitude, 345)
            radial_error += abs(math.hypot(box.x-CX, box.y-CY) - 345)
            tangential_error += math.hypot(box.x-natural[0], box.y-natural[1])
        return (elbows, total_length, tangential_error, radial_error)

    scored = sorted((score(result), i, result) for i, result in enumerate(all_solutions))
    best_score, best_index, best = scored[0]
    contest_count = len(all_solutions)
    unique_count = len(set(contest_keys))
    contest_valid = contest_count == target_solutions and unique_count == contest_count and contest_count == len(scored)
    diagnostic_print(
        f"Planet Finder {mode}: CONTEST AUDIT requested={target_solutions} contestants={contest_count} "
        f"unique={unique_count} scored={len(scored)} status={'VALID' if contest_valid else 'INVALID'}", flush=True,
    )
    for rank, (candidate_score, candidate_index, _) in enumerate(scored, 1):
        diagnostic_print(
            f"Planet Finder {mode}: CONTESTANT rank={rank} candidate={candidate_index + 1} "
            f"score[elbows={candidate_score[0]},length={candidate_score[1]:.1f},"
            f"displacement={candidate_score[2]:.1f},radial={candidate_score[3]:.1f}]", flush=True,
        )
    if not contest_valid:
        raise RuntimeError(
            f"Planet Finder {mode}: contest validity failure requested={target_solutions} contestants={contest_count} "
            f"unique={unique_count} scored={len(scored)}"
        )
    diagnostic_print(
        f"Planet Finder {mode}: selected candidate {best_index + 1}/{len(all_solutions)} "
        f"{context_label + ' ' if context_label else ''}"
        f"score[elbows={best_score[0]},length={best_score[1]:.1f},"
        f"displacement={best_score[2]:.1f},radial={best_score[3]:.1f}]", flush=True,
    )
    return best