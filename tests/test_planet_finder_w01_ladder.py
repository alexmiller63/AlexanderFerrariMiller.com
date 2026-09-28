"""Progressive W1 Planet Finder regression ladder.

Each rung adds one controlled source of W1 difficulty.  The suite is intended
to stop at the first failing rung so that a production failure is reduced to
the smallest geometry that reproduces it.
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


# Ordered from simplest to exact W1.  Keep each transition small.
LADDER = [
    ("00-separated", isolated()),
    ("01-simple-pair", isolated(Venus=100, Sun=110)),
    ("02-w1-venus-sun", isolated(Venus=W01_EXACT["Venus"], Sun=W01_EXACT["Sun"])),
    ("03-w1-inner-three", isolated(Venus=W01_EXACT["Venus"], Sun=W01_EXACT["Sun"], Mars=W01_EXACT["Mars"])),
    ("04-w1-inner-four", isolated(Mercury=W01_EXACT["Mercury"], Venus=W01_EXACT["Venus"], Sun=W01_EXACT["Sun"], Mars=W01_EXACT["Mars"])),
    ("05-w1-inner-five", isolated(Mercury=W01_EXACT["Mercury"], Venus=W01_EXACT["Venus"], Sun=W01_EXACT["Sun"], Mars=W01_EXACT["Mars"], Pluto=W01_EXACT["Pluto"])),
    ("06-add-wrap-pair", isolated(Mercury=W01_EXACT["Mercury"], Venus=W01_EXACT["Venus"], Sun=W01_EXACT["Sun"], Mars=W01_EXACT["Mars"], Pluto=W01_EXACT["Pluto"], Saturn=W01_EXACT["Saturn"], Neptune=W01_EXACT["Neptune"])),
    ("07-add-wrap-ceres", isolated(Mercury=W01_EXACT["Mercury"], Venus=W01_EXACT["Venus"], Sun=W01_EXACT["Sun"], Mars=W01_EXACT["Mars"], Pluto=W01_EXACT["Pluto"], Saturn=W01_EXACT["Saturn"], Neptune=W01_EXACT["Neptune"], Ceres=W01_EXACT["Ceres"])),
    ("08-add-wrap-moon", isolated(Mercury=W01_EXACT["Mercury"], Venus=W01_EXACT["Venus"], Sun=W01_EXACT["Sun"], Mars=W01_EXACT["Mars"], Pluto=W01_EXACT["Pluto"], Saturn=W01_EXACT["Saturn"], Neptune=W01_EXACT["Neptune"], Ceres=W01_EXACT["Ceres"], Moon=W01_EXACT["Moon"])),
    ("09-add-uranus", {**W01_EXACT, "Jupiter": 140}),
    ("10-exact-w1", W01_EXACT),
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
