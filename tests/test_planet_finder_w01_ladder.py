"""Progressive W1 Planet Finder regression ladder.

Each rung adds one controlled source of W1 difficulty. The suite stops at the
first failing rung so that a production failure is reduced to the smallest
geometry that reproduces it.
"""

import pytest

from planet_finder_geometry import CANONICAL, FinderMode
from planet_finder_search import layout
from planet_finder_validation import validate_layout


W01_EXACT = {
    "Sun": 277.511945972904,
    "Moon": 22.937571430229294,
    "Mercury": 264.1023447351197,
    "Venus": 275.4313050776394,
    "Mars": 280.39213202805865,
    "Jupiter": 111.74481470549088,
    "Saturn": 355.99936587038286,
    "Ceres": 6.453439627692317,
    "Uranus": 58.03460466327627,
    "Neptune": 359.4721293482971,
    "Pluto": 302.62909367404063,
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


def isolated(**changes):
    """Start from an intentionally easy sky, then replace selected longitudes."""
    values = {
        "Sun": 0, "Mercury": 35, "Venus": 70, "Mars": 105,
        "Jupiter": 140, "Saturn": 175, "Uranus": 210, "Neptune": 245,
        "Ceres": 280, "Pluto": 315, "Moon": 330,
    }
    values.update(changes)
    return values


def w1_pair_with_mars(mars):
    # When Venus/Sun move to W1, move synthetic Ceres out of the 275-280 degree
    # neighborhood too. Otherwise approaching Mars accidentally creates a
    # synthetic Ceres-Mars conjunction that does not exist in W1.
    return isolated(
        Ceres=70,
        Venus=W01_EXACT["Venus"],
        Sun=W01_EXACT["Sun"],
        Mars=mars,
    )


# First isolate the exact transition from the known-good W1 Venus/Sun pair to
# the real W1 Mars longitude. Only Mars changes across the approach rungs.
LADDER = [
    ("00-separated", isolated()),
    ("01-simple-pair", isolated(Venus=100, Sun=110)),
    ("02-w1-venus-sun-clean", w1_pair_with_mars(105.0)),
    ("03-mars-240", w1_pair_with_mars(240.0)),
    ("04-mars-255", w1_pair_with_mars(255.0)),
    ("05-mars-265", w1_pair_with_mars(265.0)),
    ("06-mars-270", w1_pair_with_mars(270.0)),
    ("07-mars-274", w1_pair_with_mars(274.0)),
    ("08-mars-278", w1_pair_with_mars(278.0)),
    ("09-mars-280", w1_pair_with_mars(280.0)),
    ("10-mars-w1-exact", w1_pair_with_mars(W01_EXACT["Mars"])),
]


@pytest.mark.parametrize("rung,longitudes", LADDER, ids=[item[0] for item in LADDER])
def test_w01_progressive_ladder(monkeypatch, rung, longitudes):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    source = bodies(longitudes)
    result = layout(
        FinderMode.GREEK,
        source,
        target_solutions=1,
        budget={"max_node_candidates": 2000, "max_seconds": 60.0},
        context_label=f"W01-ladder-{rung}",
    )
    validate(result, source)
