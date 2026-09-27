"""Diagnostic experiment: test every W02 recursive-body ordering independently.

This does not change production search behavior.  It bypasses layout()'s
promotion controller and asks _solve_order() the same question for each of the
six permutations of the three ordinary recursive bodies left by the 1-degree
Venus-Sun case.
"""

from itertools import permutations
import time

from planet_finder_geometry import CANONICAL, FinderMode, alignment_groups, conjunction_groups
from planet_finder_search_core import DepthNodeBudgetExhausted, _solve_order
from test_planet_finder_w02_conjunction import conjunction_case


def test_w02_one_degree_all_recursive_orderings(monkeypatch):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "2")
    bodies = conjunction_case(1.0)

    removed = {
        item[1]
        for group in conjunction_groups(bodies)
        for item in group
    }
    removed.update(
        item[1]
        for group in alignment_groups(bodies)
        for item in group
    )
    recursive = [
        (index, body)
        for index, body in enumerate(bodies)
        if body[1] not in removed
    ]

    names = [body[1] for _, body in recursive]
    assert set(names) == {"Mars", "Ceres", "Neptune"}, names

    results = []
    for attempt, order in enumerate(permutations(recursive), 1):
        order_names = " > ".join(body[1] for _, body in order)
        budget = {
            "max_node_candidates": 2000,
            "max_seconds": 15.0,
            "started": time.monotonic(),
        }
        body_attempts = {name: 0 for name in names}
        try:
            outcome = _solve_order(
                FinderMode.GREEK,
                bodies,
                list(order),
                budget,
                target_solutions=1,
                order_index=attempt,
                total_orders=6,
                context_label="w02-permutation-diagnostic",
                displacement_scale=0.25,
                body_attempts=body_attempts,
                refinement_deadline=budget["started"] + budget["max_seconds"],
            )
            kind = outcome.kind
            blocker = outcome.blocker
        except DepthNodeBudgetExhausted as exc:
            kind = "CAPPED"
            blocker = exc.name
        except RuntimeError as exc:
            kind = "RUNTIME"
            blocker = str(exc)

        print(
            f"W02 PERMUTATION RESULT attempt={attempt}/6 order={order_names} "
            f"kind={kind} blocker={blocker} attempts={body_attempts}",
            flush=True,
        )
        results.append((order_names, kind, blocker))

    assert len(results) == 6
