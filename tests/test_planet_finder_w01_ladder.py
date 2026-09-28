"""Narrow the W1 Sun/Venus/Mars search-performance boundary.

Only Mars changes. All other synthetic bodies stay away from the target cluster.
Stop at the first failure so we identify the smallest Mars approach that makes
the search pathological.
"""

import pytest

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


def geometry(mars):
    return {
        "Sun": SUN,
        "Mercury": 35,
        "Venus": VENUS,
        "Mars": mars,
        "Jupiter": 140,
        "Saturn": 175,
        "Uranus": 210,
        "Neptune": 245,
        "Ceres": 70,
        "Pluto": 315,
        "Moon": 330,
    }


MARS_APPROACH = [275.0, 276.0, 277.0, 277.5, 278.0]


@pytest.mark.parametrize("mars", MARS_APPROACH, ids=[f"mars-{m:g}" for m in MARS_APPROACH])
def test_mars_approach_boundary(monkeypatch, mars):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    source = bodies(geometry(mars))
    result = layout(
        FinderMode.GREEK,
        source,
        target_solutions=1,
        budget={"max_node_candidates": 2000, "max_seconds": 60.0},
        context_label=f"W01-mars-boundary-{mars:g}",
    )
    validate(result, source)
