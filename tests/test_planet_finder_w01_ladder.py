"""Focused W1 conjunction-to-DFS chronological trace.

Mars=275 is the smallest currently demonstrated pathological case.  This test
adds a bounded Python execution trace around the existing search function so we
can see the actual DFS enter/candidate/backtrack sequence without changing any
solver decisions.
"""

import sys

from planet_finder_geometry import CANONICAL, FinderMode
from planet_finder_search import layout
from planet_finder_validation import validate_layout

SUN = 277.511945972904
VENUS = 275.4313050776394
TRACE_LIMIT = 160


def bodies(longitudes):
    assert set(longitudes) == set(CANONICAL)
    return [(name.lower(), name, float(longitudes[name])) for name in CANONICAL]


def validate(result, source):
    expected = {name for _, name, _ in source}
    actual = [name for _, name, _, _, _ in result]
    assert len(actual) == len(expected)
    assert set(actual) == expected
    valid, errors = validate_layout(FinderMode.GREEK, result)
    assert valid, errors


def geometry():
    return {
        "Sun": SUN,
        "Mercury": 35,
        "Venus": VENUS,
        "Mars": 275.0,
        "Jupiter": 140,
        "Saturn": 175,
        "Uranus": 210,
        "Neptune": 245,
        "Ceres": 70,
        "Pluto": 315,
        "Moon": 330,
    }


def bounded_search_trace():
    """Return a sys.settrace callback that prints only search() call/return events.

    Locals expose the DFS depth, current body, candidate count, staged bodies,
    and deepest depth.  Limiting the trace keeps Actions output readable while
    preserving the chronological recursion/backtrack pattern.
    """
    state = {"events": 0}

    def tracer(frame, event, arg):
        if state["events"] >= TRACE_LIMIT:
            return tracer
        if frame.f_code.co_name != "search" or not frame.f_code.co_filename.endswith(
            "planet_finder_search_core.py"
        ):
            return tracer
        if event not in {"call", "return", "exception"}:
            return tracer

        local = frame.f_locals
        depth = local.get("depth", "?")
        order = local.get("order", ())
        body = "complete"
        if isinstance(depth, int) and depth < len(order):
            try:
                body = order[depth][1][1]
            except (IndexError, TypeError):
                body = "?"
        staged = local.get("staged", {})
        staged_names = []
        try:
            staged_names = [row[1] for _, row in sorted(staged.items())]
        except (AttributeError, IndexError, TypeError):
            pass

        state["events"] += 1
        if event == "exception":
            exc = arg[1] if isinstance(arg, tuple) and len(arg) > 1 else arg
            outcome = f" exception={type(exc).__name__}:{exc}"
        elif event == "return":
            outcome = f" result={arg!r}"
        else:
            outcome = ""
        print(
            f"DFS-TRACE {state['events']:03d} {event.upper()} "
            f"depth={depth} body={body} "
            f"candidates={local.get('candidates', '?')} "
            f"backtracks={local.get('backtracks', '?')} "
            f"deepest={local.get('deepest', '?')} "
            f"staged={staged_names}{outcome}",
            flush=True,
        )
        if state["events"] == TRACE_LIMIT:
            print(f"DFS-TRACE LIMIT reached={TRACE_LIMIT}; further trace suppressed", flush=True)
        return tracer

    return tracer


def test_mars_275_chronological_dfs_trace(monkeypatch):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")
    source = bodies(geometry())
    tracer = bounded_search_trace()
    sys.settrace(tracer)
    try:
        result = layout(
            FinderMode.GREEK,
            source,
            target_solutions=1,
            budget={"max_node_candidates": 2000, "max_seconds": 60.0},
            context_label="W01-mars-275-chronological-trace",
        )
    finally:
        sys.settrace(None)
    validate(result, source)
