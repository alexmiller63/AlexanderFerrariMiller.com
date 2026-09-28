"""Isolated timing test for the first failing W1-approach geometry.

Mars=278 degrees is the first case that exceeded the 60 second regression
clock. Give exactly that geometry 180 seconds before changing solver logic.
"""

from planet_finder_geometry import CANONICAL, FinderMode
from planet_finder_search import layout
from planet_finder_validation import validate_layout


W01_EXACT = {
    "Sun": 277.511945972904,
    "Venus": 275.4313050776394,
}


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


def mars_278_geometry():
    # Keep all non-target bodies well away from the W1 Venus/Sun/Mars cluster.
    return {
        "Sun": W01_EXACT["Sun"],
        "Mercury": 35,
        "Venus": W01_EXACT["Venus"],
        "Mars": 278.0,
        "Jupiter": 140,
        "Saturn": 175,
        "Uranus": 210,
        "Neptune": 245,
        "Ceres": 70,
        "Pluto": 315,
        "Moon": 330,
    }


def test_mars_278_with_180_second_clock(monkeypatch):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    source = bodies(mars_278_geometry())
    result = layout(
        FinderMode.GREEK,
        source,
        target_solutions=1,
        budget={"max_node_candidates": 2000, "max_seconds": 180.0},
        context_label="W01-mars-278-180s",
    )
    validate(result, source)
