"""Progressive full-system QA for the Planet Finder controller.

These tests deliberately exercise layout(), not just geometry classifiers.
A green classifier suite is not sufficient: the production state machine must
complete the same conjunction/alignment/general-search phases used by a week.
"""

import math

import pytest

from planet_finder_geometry import CANONICAL, CX, CY, FinderMode, alignment_groups, conjunction_groups
from planet_finder_search import layout
from planet_finder_validation import validate_layout


MODES = [FinderMode.GREEK, FinderMode.LATIN, FinderMode.MIXED]


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


def assert_alignment_labels_follow_lambda(result, bodies):
    """The text labels in a planned alignment retain their circular order."""
    boxes = {name: box for _, name, _, box, _ in result}
    for group in alignment_groups(bodies):
        reference = group[0][2] - 90.0
        angles = []
        for _, name, _ in group:
            box = boxes[name]
            longitude = (math.degrees(math.atan2(CY - box.y, box.x - CX)) - 180.0) % 360.0
            angles.append((longitude - reference) % 360.0)
        assert angles == sorted(angles), [item[1] for item in group]


def w1_shaped_bodies():
    """Five aligned + four aligned + two ordinary canonical bodies."""
    longitudes = {
        "Sun": 0, "Mercury": 5, "Venus": 10, "Mars": 15, "Pluto": 20,
        "Saturn": 100, "Neptune": 107, "Ceres": 114, "Moon": 121,
        "Uranus": 180, "Jupiter": 240,
    }
    assert set(longitudes) == set(CANONICAL)
    return synthetic_bodies(longitudes)


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

# Keep non-target bodies outside 30 degrees of the five-body laboratory.  The
# previous fixture accidentally put Jupiter at 240 degrees, so it joined the
# Mercury-to-Pluto alignment and turned a five-body test into a six-body test.
ISOLATED_OTHERS = {
    "Saturn": 20,
    "Neptune": 60,
    "Ceres": 100,
    "Moon": 140,
    "Uranus": 180,
    "Jupiter": 220,
}


def five_body_stage(mercury, venus, sun, mars, pluto):
    values = dict(ISOLATED_OTHERS)
    values.update({
        "Mercury": mercury,
        "Venus": venus,
        "Sun": sun,
        "Mars": mars,
        "Pluto": pluto,
    })
    return values


# Tighten only the real five-body group.  Stages preserve ordering while moving
# from comfortable spacing toward the captured W01 geometry.  The final stage
# is exact for those five bodies; ordinary bodies remain isolated.
TIGHT_FIVE_LADDER = [
    ("five-easy", five_body_stage(260, 270, 280, 290, 300)),
    ("five-medium", five_body_stage(264.1023447351197, 273, 280, 287, 302.62909367404063)),
    ("five-tight-venus-sun", five_body_stage(264.1023447351197, 275.4313050776394, 277.511945972904, 287, 302.62909367404063)),
    ("five-tight-inner-three", five_body_stage(264.1023447351197, 275.4313050776394, 277.511945972904, 280.39213202805865, 302.62909367404063)),
    ("five-exact", five_body_stage(
        W01_EXACT["Mercury"], W01_EXACT["Venus"], W01_EXACT["Sun"],
        W01_EXACT["Mars"], W01_EXACT["Pluto"]
    )),
]

# Broader system ladder retained after the isolated five-body laboratory.
W01_LADDER = [
    ("easy", {
        "Sun": 0, "Mercury": 5, "Venus": 10, "Mars": 15, "Pluto": 20,
        "Saturn": 100, "Neptune": 107, "Ceres": 114, "Moon": 121,
        "Uranus": 180, "Jupiter": 240,
    }),
    ("wrap-four", {
        "Sun": 180, "Mercury": 185, "Venus": 190, "Mars": 195, "Pluto": 200,
        "Saturn": 355.99936587038286, "Neptune": 359.4721293482971,
        "Ceres": 6.453439627692317, "Moon": 22.937571430229294,
        "Uranus": 80, "Jupiter": 120,
    }),
    ("both-real-alignments", {
        "Mercury": 264.1023447351197, "Venus": 275.4313050776394,
        "Sun": 277.511945972904, "Mars": 280.39213202805865,
        "Pluto": 302.62909367404063,
        "Saturn": 355.99936587038286, "Neptune": 359.4721293482971,
        "Ceres": 6.453439627692317, "Moon": 22.937571430229294,
        "Uranus": 80, "Jupiter": 120,
    }),
    ("exact-W01", W01_EXACT),
]


def test_level_10_w1_shaped_classification_has_two_large_alignments():
    bodies = w1_shaped_bodies()
    assert conjunction_groups(bodies) == []
    groups = group_names(alignment_groups(bodies))
    assert groups == [
        ["Sun", "Mercury", "Venus", "Mars", "Pluto"],
        ["Saturn", "Neptune", "Ceres", "Moon"],
    ]


@pytest.mark.parametrize("mode", MODES)
def test_level_11_w1_shaped_full_state_machine_completes(monkeypatch, mode):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    bodies = w1_shaped_bodies()
    result = layout(
        mode, bodies, target_solutions=1,
        budget={"max_node_candidates": 200, "max_seconds": 30.0},
        context_label=f"synthetic-W01-{mode.value}",
    )
    assert_complete_valid_layout(result, bodies, mode)


@pytest.mark.parametrize("mode", MODES)
def test_level_12_w1_shaped_full_state_machine_is_deterministic(monkeypatch, mode):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    bodies = w1_shaped_bodies()
    budget = {"max_node_candidates": 200, "max_seconds": 30.0}
    first = layout(mode, bodies, target_solutions=1, budget=budget, context_label=f"determinism-{mode.value}-A")
    second = layout(mode, bodies, target_solutions=1, budget=budget, context_label=f"determinism-{mode.value}-B")
    assert_complete_valid_layout(first, bodies, mode)
    assert_complete_valid_layout(second, bodies, mode)
    assert first == second


@pytest.mark.parametrize("level,longitudes", TIGHT_FIVE_LADDER, ids=[item[0] for item in TIGHT_FIVE_LADDER])
@pytest.mark.parametrize("mode", MODES)
def test_level_15_isolated_tight_five_breakpoint(monkeypatch, mode, level, longitudes):
    """Locate the first failing geometry inside the real W01 five-body group."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    bodies = synthetic_bodies(longitudes)
    groups = group_names(alignment_groups(bodies))
    target = {"Mercury", "Venus", "Sun", "Mars", "Pluto"}
    matching = [group for group in groups if set(group) == target]
    assert len(matching) == 1, groups
    result = layout(
        mode, bodies, target_solutions=1,
        budget={"max_node_candidates": 2000,
                "max_seconds": 15.0 if mode == FinderMode.GREEK else 60.0},
        context_label=f"tight-five-{level}-{mode.value}",
    )
    assert_complete_valid_layout(result, bodies, mode)


@pytest.mark.parametrize("level,longitudes", W01_LADDER, ids=[item[0] for item in W01_LADDER])
@pytest.mark.parametrize("mode", MODES)
def test_level_20_progressive_real_w01_geometry(monkeypatch, mode, level, longitudes):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    bodies = synthetic_bodies(longitudes)
    result = layout(
        mode, bodies, target_solutions=1,
        budget={"max_node_candidates": 2000,
                "max_seconds": 15.0 if mode == FinderMode.GREEK else 60.0},
        context_label=f"regression-{level}-{mode.value}",
    )
    assert_complete_valid_layout(result, bodies, mode)
    if level in ("both-real-alignments", "exact-W01") and mode != FinderMode.GREEK:
        assert_alignment_labels_follow_lambda(result, bodies)
