"""Progressive full-system QA for the Planet Finder controller.

These tests deliberately exercise layout(), not just geometry classifiers.
A green classifier suite is not sufficient: the production state machine must
complete the same conjunction/alignment/general-search phases used by a week.
"""

import pytest

from planet_finder_geometry import CANONICAL, FinderMode, alignment_groups, conjunction_groups
from planet_finder_search import layout
from planet_finder_validation import validate_layout


def synthetic_bodies(longitudes):
    """Return all canonical bodies with deterministic synthetic longitudes."""
    assert set(longitudes) == set(CANONICAL)
    return [(name.lower(), name, float(longitudes[name])) for name in CANONICAL]


def group_names(groups):
    return [[item[1] for item in group] for group in groups]


def assert_complete_valid_layout(result, bodies, mode=FinderMode.GREEK):
    expected = {name for _, name, _ in bodies}
    actual = [name for _, name, _, _, _ in result]
    assert len(actual) == len(expected)
    assert len(actual) == len(set(actual))
    assert set(actual) == expected
    valid, errors = validate_layout(mode, result)
    assert valid, errors


def w1_shaped_bodies():
    """Five aligned + four aligned + two ordinary canonical bodies."""
    longitudes = {
        "Sun": 0, "Mercury": 5, "Venus": 10, "Mars": 15, "Pluto": 20,
        "Saturn": 100, "Neptune": 107, "Ceres": 114, "Moon": 121,
        "Uranus": 180, "Jupiter": 240,
    }
    assert set(longitudes) == set(CANONICAL)
    return synthetic_bodies(longitudes)


# Exact production input captured from ISO 2026-W01 on 2026-09-26.  This is a
# regression fixture, not an ephemeris calculation: tests remain deterministic.
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

# Progressive difficulty ladder.  Level 0 is the already-green convenient
# geometry.  Levels 1-3 independently introduce the two real W01 stressors;
# level 4 is the exact production geometry.  This tells us where reality first
# exceeds the controller instead of reducing W01 to a single red/green result.
W01_LADDER = [
    (
        "easy",
        {
            "Sun": 0, "Mercury": 5, "Venus": 10, "Mars": 15, "Pluto": 20,
            "Saturn": 100, "Neptune": 107, "Ceres": 114, "Moon": 121,
            "Uranus": 180, "Jupiter": 240,
        },
    ),
    (
        "tight-five",
        {
            "Mercury": 264.1023447351197, "Venus": 275.4313050776394,
            "Sun": 277.511945972904, "Mars": 280.39213202805865,
            "Pluto": 302.62909367404063,
            "Saturn": 100, "Neptune": 107, "Ceres": 114, "Moon": 121,
            "Uranus": 180, "Jupiter": 240,
        },
    ),
    (
        "wrap-four",
        {
            "Sun": 180, "Mercury": 185, "Venus": 190, "Mars": 195, "Pluto": 200,
            "Saturn": 355.99936587038286, "Neptune": 359.4721293482971,
            "Ceres": 6.453439627692317, "Moon": 22.937571430229294,
            "Uranus": 80, "Jupiter": 120,
        },
    ),
    (
        "both-real-alignments",
        {
            "Mercury": 264.1023447351197, "Venus": 275.4313050776394,
            "Sun": 277.511945972904, "Mars": 280.39213202805865,
            "Pluto": 302.62909367404063,
            "Saturn": 355.99936587038286, "Neptune": 359.4721293482971,
            "Ceres": 6.453439627692317, "Moon": 22.937571430229294,
            "Uranus": 80, "Jupiter": 120,
        },
    ),
    ("exact-W01", W01_EXACT),
]


def test_level_10_w1_shaped_classification_has_two_large_alignments():
    """Five aligned + four aligned + two ordinary bodies, like W01's shape."""
    bodies = w1_shaped_bodies()
    assert conjunction_groups(bodies) == []
    groups = group_names(alignment_groups(bodies))
    assert groups == [
        ["Sun", "Mercury", "Venus", "Mars", "Pluto"],
        ["Saturn", "Neptune", "Ceres", "Moon"],
    ]


def test_level_11_w1_shaped_full_state_machine_completes(monkeypatch):
    """Acceptance gate: recursive alignment layer must coexist with general DFS."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    bodies = w1_shaped_bodies()
    result = layout(
        FinderMode.GREEK,
        bodies,
        target_solutions=1,
        budget={"max_node_candidates": 200, "max_seconds": 30.0},
        context_label="synthetic-W01",
    )
    assert_complete_valid_layout(result, bodies)


def test_level_12_w1_shaped_full_state_machine_is_deterministic(monkeypatch):
    """Identical inputs must select identical complete geometry."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    bodies = w1_shaped_bodies()
    budget = {"max_node_candidates": 200, "max_seconds": 30.0}
    first = layout(FinderMode.GREEK, bodies, target_solutions=1, budget=budget, context_label="determinism-A")
    second = layout(FinderMode.GREEK, bodies, target_solutions=1, budget=budget, context_label="determinism-B")
    assert_complete_valid_layout(first, bodies)
    assert_complete_valid_layout(second, bodies)
    assert first == second


@pytest.mark.parametrize("level,longitudes", W01_LADDER, ids=[item[0] for item in W01_LADDER])
def test_level_20_progressive_real_w01_geometry(monkeypatch, level, longitudes):
    """Find the first geometric step at which the production controller breaks."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    bodies = synthetic_bodies(longitudes)
    result = layout(
        FinderMode.GREEK,
        bodies,
        target_solutions=1,
        budget={"max_node_candidates": 2000, "max_seconds": 15.0},
        context_label=f"regression-{level}",
    )
    assert_complete_valid_layout(result, bodies)
