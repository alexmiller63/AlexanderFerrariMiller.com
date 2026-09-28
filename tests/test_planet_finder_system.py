"""Progressive full-system QA for the Planet Finder controller.

These tests deliberately exercise layout(), not just geometry classifiers.
A green classifier suite is not sufficient: the production state machine must
complete the same conjunction/alignment/general-search phases used by a week.
"""

import math

import pytest

from planet_finder_geometry import CANONICAL, CX, CY, FinderMode, alignment_groups, conjunction_groups
from planet_finder_search import layout
from planet_finder_search_core import _search_alignment_fallback
from planet_finder_validation import validate_layout


MODES = [FinderMode.GREEK, FinderMode.LATIN, FinderMode.MIXED]


def test_blocked_preplacement_restores_alignment_before_recursive_retry():
    """A dead ordinary-body search must release its planned alignment."""
    placed = ["conjunction", "planned box"]
    leaders = ["conjunction path", "planned path"]
    leader_names = ["conjunction name", "aligned name"]
    staged = {0: "conjunction row", 1: "planned row"}
    groups = [[(1, ("symbol", "aligned name", 30.0))]]
    calls = []

    def search(depth):
        assert depth == 0
        calls.append("planned search")
        assert staged[1] == "planned row"
        return False

    def recursive(group_index):
        assert group_index == 0
        calls.append("recursive retry")
        assert placed == ["conjunction"]
        assert leaders == ["conjunction path"]
        assert leader_names == ["conjunction name"]
        assert staged == {0: "conjunction row"}
        return True

    assert _search_alignment_fallback(
        ({"aligned name": "planned box"}, {"aligned name": "planned path"}),
        groups, placed, leaders, leader_names, staged, search, recursive,
    )
    assert calls == ["planned search", "recursive retry"]


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

W02_EXACT = {
    "Sun": 284.6440014763892,
    "Moon": 126.1796456120117,
    "Mercury": 274.8007325297467,
    "Venus": 284.23931723550777,
    "Mars": 285.7588826483691,
    "Jupiter": 110.82906185524807,
    "Saturn": 356.41276254486604,
    "Ceres": 7.9496046464005525,
    "Uranus": 57.84492478754409,
    "Neptune": 359.5610441804245,
    "Pluto": 302.8404789942358,
}

# Keep non-target bodies outside 30 degrees of the five-body laboratory.
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
        "Mercury": mercury, "Venus": venus, "Sun": sun,
        "Mars": mars, "Pluto": pluto,
    })
    return values


TIGHT_FIVE_LADDER = [
    ("five-easy", five_body_stage(260, 270, 280, 290, 300)),
    ("five-medium", five_body_stage(264.1023447351197, 273, 280, 287, 302.62909367404063)),
    ("five-tight-venus-sun", five_body_stage(264.1023447351197, 275.4313050776394, 277.511945972904, 287, 302.62909367404063)),
    ("five-tight-inner-three", five_body_stage(264.1023447351197, 275.4313050776394, 277.511945972904, 280.39213202805865, 302.62909367404063)),
    ("five-exact", five_body_stage(W01_EXACT["Mercury"], W01_EXACT["Venus"], W01_EXACT["Sun"], W01_EXACT["Mars"], W01_EXACT["Pluto"])),
]

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

W02_LADDER = [
    ("separated", {
        "Sun": 0, "Mercury": 40, "Venus": 80, "Mars": 120, "Pluto": 160,
        "Saturn": 200, "Neptune": 240, "Ceres": 280, "Moon": 320,
        "Uranus": 60, "Jupiter": 180,
    }),
    ("venus-sun-conjunction", {
        "Venus": 100.0, "Sun": 100.405, "Mercury": 20, "Mars": 150,
        "Pluto": 190, "Saturn": 230, "Neptune": 270, "Ceres": 310,
        "Moon": 350, "Uranus": 50, "Jupiter": 200,
    }),
    ("inner-alignment", {
        "Mercury": 274.8007325297467, "Venus": 284.23931723550777,
        "Sun": 284.6440014763892, "Mars": 285.7588826483691,
        "Pluto": 302.8404789942358, "Saturn": 20, "Neptune": 60,
        "Ceres": 100, "Moon": 140, "Uranus": 180, "Jupiter": 220,
    }),
    ("outer-wrap-alignment", {
        "Saturn": 356.41276254486604, "Neptune": 359.5610441804245,
        "Ceres": 7.9496046464005525, "Mercury": 60, "Venus": 100,
        "Sun": 140, "Mars": 180, "Pluto": 220, "Moon": 260,
        "Uranus": 300, "Jupiter": 100,
    }),
    ("jupiter-moon-alignment", {
        "Jupiter": 110.82906185524807, "Moon": 126.1796456120117,
        "Mercury": 10, "Venus": 50, "Sun": 90, "Mars": 170,
        "Pluto": 210, "Saturn": 250, "Neptune": 290, "Ceres": 330,
        "Uranus": 200,
    }),
    ("all-W02-groups", {
        "Mercury": W02_EXACT["Mercury"], "Venus": W02_EXACT["Venus"],
        "Sun": W02_EXACT["Sun"], "Mars": W02_EXACT["Mars"],
        "Pluto": W02_EXACT["Pluto"], "Saturn": W02_EXACT["Saturn"],
        "Neptune": W02_EXACT["Neptune"], "Ceres": W02_EXACT["Ceres"],
        "Jupiter": W02_EXACT["Jupiter"], "Moon": W02_EXACT["Moon"],
        "Uranus": 180,
    }),
    ("exact-W02", W02_EXACT),
]


def test_level_10_w1_shaped_classification_has_two_large_alignments():
    bodies = w1_shaped_bodies()
    assert conjunction_groups(bodies) == []
    groups = group_names(alignment_groups(bodies))
    assert groups == [["Sun", "Mercury", "Venus", "Mars", "Pluto"], ["Saturn", "Neptune", "Ceres", "Moon"]]


@pytest.mark.parametrize("mode", MODES)
def test_level_11_w1_shaped_full_state_machine_completes(monkeypatch, mode):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    bodies = w1_shaped_bodies()
    seconds = 45.0 if mode == FinderMode.GREEK else 30.0
    result = layout(mode, bodies, target_solutions=1, budget={"max_node_candidates": 200, "max_seconds": seconds}, context_label=f"synthetic-W01-{mode.value}")
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
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    bodies = synthetic_bodies(longitudes)
    groups = group_names(alignment_groups(bodies))
    target = {"Mercury", "Venus", "Sun", "Mars", "Pluto"}
    matching = [group for group in groups if set(group) == target]
    assert len(matching) == 1, groups
    result = layout(mode, bodies, target_solutions=1, budget={"max_node_candidates": 2000, "max_seconds": 15.0 if mode == FinderMode.GREEK else 60.0}, context_label=f"tight-five-{level}-{mode.value}")
    assert_complete_valid_layout(result, bodies, mode)


@pytest.mark.parametrize("level,longitudes", W01_LADDER, ids=[item[0] for item in W01_LADDER])
@pytest.mark.parametrize("mode", MODES)
def test_level_20_progressive_real_w01_geometry(monkeypatch, mode, level, longitudes):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    bodies = synthetic_bodies(longitudes)
    result = layout(mode, bodies, target_solutions=1, budget={"max_node_candidates": 2000, "max_seconds": 15.0 if mode == FinderMode.GREEK else 60.0}, context_label=f"regression-{level}-{mode.value}")
    assert_complete_valid_layout(result, bodies, mode)
    if level in ("both-real-alignments", "exact-W01") and mode != FinderMode.GREEK:
        assert_alignment_labels_follow_lambda(result, bodies)


@pytest.mark.parametrize("level,longitudes", W02_LADDER, ids=[item[0] for item in W02_LADDER])
def test_level_30_progressive_real_w02_greek_breakpoint(monkeypatch, level, longitudes):
    """Find the first W02 geometry that makes Greek preplacement explode."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    bodies = synthetic_bodies(longitudes)
    result = layout(
        FinderMode.GREEK, bodies, target_solutions=1,
        budget={"max_node_candidates": 2000, "max_seconds": 15.0},
        context_label=f"W02-ladder-{level}",
    )
    assert_complete_valid_layout(result, bodies, FinderMode.GREEK)
