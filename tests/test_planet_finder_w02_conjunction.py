"""Progressively isolate the W02 Venus-Sun conjunction breakpoint."""

import pytest

from planet_finder_geometry import CANONICAL, FinderMode
from planet_finder_search import layout
from planet_finder_validation import validate_layout


def conjunction_case(separation):
    longitudes = {
        "Venus": 100.0,
        "Sun": 100.0 + separation,
        "Mercury": 20,
        "Mars": 150,
        "Pluto": 190,
        "Saturn": 230,
        "Neptune": 270,
        "Ceres": 310,
        "Moon": 350,
        "Uranus": 50,
        "Jupiter": 200,
    }
    assert set(longitudes) == set(CANONICAL)
    return [(name.lower(), name, float(longitudes[name])) for name in CANONICAL]


@pytest.mark.parametrize(
    "separation",
    [1.0, 0.5],
    ids=["1deg", "0.5deg"],
)
def test_greek_venus_sun_separation_ladder(monkeypatch, separation):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "2")
    bodies = conjunction_case(separation)
    result = layout(
        FinderMode.GREEK,
        bodies,
        target_solutions=1,
        budget={"max_node_candidates": 2000, "max_seconds": 15.0},
        context_label=f"venus-sun-{separation:.3f}deg",
    )
    expected = {name for _, name, _ in bodies}
    actual = [name for _, name, _, _, _ in result]
    assert len(actual) == len(expected)
    assert set(actual) == expected
    valid, errors = validate_layout(FinderMode.GREEK, result)
    assert valid, errors
