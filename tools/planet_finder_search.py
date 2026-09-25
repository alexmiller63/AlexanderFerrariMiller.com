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

    if target_solutions is None:
        target_solutions = max(1, int(os.environ.get("PLANET_FINDER_CANDIDATES", str(DEFAULT_CANDIDATE_LAYOUTS))))

    if budget is None:
        budget = new_search_budget()

    # One clock per mode, always.  Copy the limits so callers may safely reuse
    # one configuration object without ever sharing elapsed time between Greek,
    # Latin, and Mixed.
    budget = dict(budget)
    budget["started"] = time.monotonic()
    diagnostic_print(
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
    # Keep one wall clock per notation mode, but reserve an equal cumulative
    # share for each refinement so a coarse geometry cannot consume time that
    # belongs to the finer fallback geometries.
    refinement_deadlines = tuple(
        budget["started"] + budget["max_seconds"] * (i + 1) / len(refinement_scales)
        for i in range(len(refinement_scales))
    )
    attempted_orders = set()
    # A body may be promoted at most once at each placement refinement.
    # Seeing the same squeaky wheel again closes that refinement's bounded
    # promotion cycle instead of generating another tail permutation.
    promoted_bodies = set()
    # One per-body candidate cap for the current placement refinement.
    # Reordering may reset a promoted body's budget; changing refinement resets
    # every body's budget because the candidate geometry has changed.
    # Forward-check probes are deliberately outside this accounting.
    body_attempts = {name: 0 for _, (_, name, _) in indexed}
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

    def next_promotion_order(current_order, body_name):
        """Return the next bounded ordering for a squeaky-wheel body.

        Try the body at the zero position first, then immediately to its
        right, then at the opposite side of the linearized order.  Relative
        order of every other body is preserved.  This explores the two sides
        of a crowded front position without opening arbitrary permutations.
        """
        body_index = next(
            (i for i, item in enumerate(current_order) if item[1][1] == body_name),
            None,
        )
        if body_index is None:
            return None
        body_item = current_order[body_index]
        rest = [item for i, item in enumerate(current_order) if i != body_index]
        candidate_orders = [
            [body_item, *rest],
            [rest[0], body_item, *rest[1:]],
            [*rest, body_item],
        ]
        for candidate in candidate_orders:
            names = tuple(item[1][1] for item in candidate)
            if (refinement_index, names) not in attempted_orders:
                return candidate
        return None

    while state != "SCORE":

        now = time.monotonic()
        if now - budget["started"] >= budget["max_seconds"]:
            raise RuntimeError(
                f"Planet Finder {mode} mode wall-clock budget exhausted "
                f"(limit {budget['max_seconds']:.1f}s)"
            )
        if state != "REFINE" and now >= refinement_deadlines[refinement_index]:
            if refinement_index + 1 >= len(refinement_scales):
                raise RuntimeError(
                    f"Planet Finder {mode} mode wall-clock budget exhausted "
                    f"(limit {budget['max_seconds']:.1f}s)"
                )
            diagnostic_print(
                f"Planet Finder {mode}: REFINEMENT TIME SLICE EXHAUSTED "
                f"at {refinement_scales[refinement_index]:g} label-lengths; "
                f"elapsed={now - budget['started']:.1f}s; advancing",
                flush=True,
            )
            state = "REFINE"
            continue

        if state == "REFINE":
            if refinement_index + 1 >= len(refinement_scales):
                final_sequence = " > ".join(item[1][1] for item in order)
                diagnostic_print(
                    f"Planet Finder {mode}: TERMINAL SEARCH DIAGNOSTIC "
                    f"refinements={len(refinement_scales)} attempts={len(refinement_history)} "
                    f"final-sequence={final_sequence}",
                    flush=True,
                )
                for i, event in enumerate(refinement_history, 1):
                    diagnostic_print(
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
            # into the finer search, while resetting all search-work budgets
            # because the candidate geometry has changed.
            attempted_orders.clear()
            promoted_bodies.clear()
            for name in body_attempts:
                body_attempts[name] = 0
            promote_body = None
            diagnostic_print(
                f"Planet Finder {mode}: REFINEMENT ADVANCE "
                f"to {refinement_scales[refinement_index]:g} label-lengths; "
                "resetting candidate budgets; preserving learned sequence="
                + " > ".join(item[1][1] for item in order),
                flush=True,
            )
            state = "SEARCH_ORDER"
            continue

        if state == "CAPPED":
            # A node cap means this ordering was not searched to completion.
            # Promote a squeaky wheel only once at this refinement. If the
            # same body becomes the squeaky wheel again, the bounded promotion
            # cycle is closed and the controller advances placement refinement.
            if promote_body in promoted_bodies:
                diagnostic_print(
                    f"Planet Finder {mode}: CAPPED PROMOTION REPEAT body={promote_body}; "
                    f"promoted={len(promoted_bodies)}/{len(indexed)} "
                    f"at {refinement_scales[refinement_index]:g} label-lengths; refining",
                    flush=True,
                )
                state = "REFINE"
                continue
            promoted_bodies.add(promote_body)
            promoted_order = next_promotion_order(order, promote_body)
            if promoted_order is None:
                cycle_names = " > ".join(item[1][1] for item in order)
                diagnostic_print(
                    f"Planet Finder {mode}: CAPPED SIDEWAYS CYCLE CLOSED body={promote_body}; "
                    f"promotions/orderings={len(attempted_orders)} "
                    f"at {refinement_scales[refinement_index]:g} label-lengths "
                    f"sequence={cycle_names}; refining",
                    flush=True,
                )
                state = "REFINE"
                continue
            promoted_names = tuple(item[1][1] for item in promoted_order)
            # A capped body gets a fresh 200-candidate budget when the state
            # machine promotes it. The cap is therefore per-body/per-ordering
            # search work, not a lifetime quota for the entire mode. Forward
            # checking remains outside this accounting.
            body_attempts[promote_body] = 0
            order = promoted_order
            diagnostic_print(
                f"Planet Finder {mode}: CAPPED PROMOTE body={promote_body}; "
                f"reset candidate budget to 0/{budget['max_node_candidates']:,}; "
                "incomplete search, preserving refinement and restarting sequence="
                + " > ".join(promoted_names),
                flush=True,
            )
            state = "SEARCH_ORDER"
            continue

        if state == "PROMOTE":
            if promote_body in promoted_bodies:
                diagnostic_print(
                    f"Planet Finder {mode}: PROMOTION REPEAT body={promote_body}; "
                    f"promoted={len(promoted_bodies)}/{len(indexed)} "
                    f"at {refinement_scales[refinement_index]:g} label-lengths; refining",
                    flush=True,
                )
                state = "REFINE"
                continue
            promoted_bodies.add(promote_body)
            promoted_order = next_promotion_order(order, promote_body)
            if promoted_order is None:
                diagnostic_print(
                    f"Planet Finder {mode}: PROMOTION SIDEWAYS CYCLE CLOSED body={promote_body} "
                    f"at {refinement_scales[refinement_index]:g} label-lengths; refining",
                    flush=True,
                )
                state = "REFINE"
            else:
                promoted_names = tuple(item[1][1] for item in promoted_order)
                order = promoted_order
                diagnostic_print(
                    f"Planet Finder {mode}: PROMOTE/SIDEWAYS body={promote_body}; "
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
        diagnostic_print(
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
                body_attempts=body_attempts,
                refinement_deadline=refinement_deadlines[refinement_index],
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

        if outcome.kind == "INCONCLUSIVE":
            diagnostic_print(
                f"Planet Finder {mode}: SEARCH INCONCLUSIVE "
                f"body={outcome.blocker} refinement={refinement_scales[refinement_index]:g} "
                f"orders={len(attempted_orders)}; bounded search closed without "
                f"establishing {target_solutions} contestants",
                flush=True,
            )
            raise RuntimeError(
                f"Planet Finder {mode}: bounded search inconclusive; "
                f"no valid {target_solutions}-contestant contest was established"
            )

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
        diagnostic_print(
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
    diagnostic_print(
        f"Planet Finder {mode}: CONTEST AUDIT "
        f"requested={target_solutions} contestants={contest_count} "
        f"unique={unique_count} scored={len(scored)} "
        f"status={'VALID' if contest_valid else 'INVALID'}",
        flush=True,
    )
    for rank, (candidate_score, candidate_index, _) in enumerate(scored, 1):
        diagnostic_print(
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

    diagnostic_print(
        f"Planet Finder {mode}: selected candidate {best_index + 1}/{len(all_solutions)} "
        f"{context_label + ' ' if context_label else ''}"
        f"score[elbows={best_score[0]},length={best_score[1]:.1f},"
        f"displacement={best_score[2]:.1f},radial={best_score[3]:.1f}]",
        flush=True,
    )
    return best