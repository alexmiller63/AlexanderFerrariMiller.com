"""Focused W1 conjunction-to-DFS handoff diagnostic.

Mars=275 is the smallest currently demonstrated pathological case.  Keep the
geometry fixed and turn on forensic diagnostics so the existing search-core
instrumentation reports which downstream body/constraint consumes each blob
branch.  This intentionally changes no solver behavior.
"""

from planet_finder_geometry import CANONICAL, FinderMode
from planet_finder_search import layout
from planet_finder_validation import validate_layout

SUN = 277.511945972904
VENUS = 275.4313050776394


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


def test_mars_275_downstream_handoff(monkeypatch):
    # Existing level-3 diagnostics include capped-body summaries, terminal
    # rejection constraints, best partial depth, and conjunction branch events.
    # Use them as a probe before changing conjunction/DFS semantics.
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "3")
    source = bodies(geometry())
    result = layout(
        FinderMode.GREEK,
        source,
        target_solutions=1,
        budget={"max_node_candidates": 2000, "max_seconds": 60.0},
        context_label="W01-mars-275-handoff-diagnostic",
    )
    validate(result, source)
