"""Progressive full-system QA for the Planet Finder controller.

These tests deliberately exercise layout(), not just geometry classifiers.
A green classifier suite is not sufficient: the production state machine must
complete the same conjunction/alignment/general-search phases used by a week.
"""

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


def test_level_10_w1_shaped_classification_has_two_large_alignments():
    """Five aligned + four aligned + three ordinary bodies, like W01's shape."""
    bodies = synthetic_bodies({
        "Sun": 0, "Mercury": 5, "Venus": 10, "Mars": 15, "Pluto": 20,
        "Saturn": 100, "Neptune": 107, "Ceres": 114, "Moon": 121,
        "Uranus": 180, "Jupiter": 240, "Earth": 300,
    })
    assert conjunction_groups(bodies) == []
    groups = group_names(alignment_groups(bodies))
    assert groups == [
        ["Sun", "Mercury", "Venus", "Mars", "Pluto"],
        ["Saturn", "Neptune", "Ceres", "Moon"],
    ]


def test_level_11_w1_shaped_full_state_machine_completes(monkeypatch):
    """Acceptance gate: recursive alignment layer must coexist with general DFS."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    bodies = synthetic_bodies({
        "Sun": 0, "Mercury": 5, "Venus": 10, "Mars": 15, "Pluto": 20,
        "Saturn": 100, "Neptune": 107, "Ceres": 114, "Moon": 121,
        "Uranus": 180, "Jupiter": 240, "Earth": 300,
    })
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
    bodies = synthetic_bodies({
        "Sun": 0, "Mercury": 5, "Venus": 10, "Mars": 15, "Pluto": 20,
        "Saturn": 100, "Neptune": 107, "Ceres": 114, "Moon": 121,
        "Uranus": 180, "Jupiter": 240, "Earth": 300,
    })
    budget = {"max_node_candidates": 200, "max_seconds": 30.0}
    first = layout(FinderMode.GREEK, bodies, target_solutions=1, budget=budget, context_label="determinism-A")
    second = layout(FinderMode.GREEK, bodies, target_solutions=1, budget=budget, context_label="determinism-B")
    assert_complete_valid_layout(first, bodies)
    assert_complete_valid_layout(second, bodies)
    assert first == second
