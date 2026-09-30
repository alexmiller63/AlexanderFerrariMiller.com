"""Focused W36 plus W01/W02 Planet Finder diagnostic ladders.

W36 is the hard-won production baseline. Its focused ladder isolates the two
breakpoints found by the broad ladder: Uranus for Greek/Latin, and interaction
among the three real alignment groups for Mixed. Production solver code is
untouched.
"""

import pytest

from planet_finder_geometry import FinderMode
from planet_finder_search import layout
from test_planet_finder_system import (
    W01_LADDER,
    W02_LADDER,
    assert_alignment_labels_follow_lambda,
    assert_complete_valid_layout,
    synthetic_bodies,
)

MODES = [FinderMode.GREEK, FinderMode.LATIN, FinderMode.MIXED]
LADDER_SECONDS = 15.0
REGRESSION_SECONDS = 60.0

W36_KNOWN_GOOD = {
    "Sun": 157 + 38 / 60,
    "Moon": 11 + 53 / 60,
    "Mercury": 160 + 48 / 60,
    "Venus": 180 + 22 + 22 / 60,
    "Mars": 90 + 12 + 46 / 60,
    "Jupiter": 120 + 13 + 29 / 60,
    "Saturn": 13 + 44 / 60,
    "Ceres": 90 + 6 + 33 / 60,
    "Uranus": 60 + 5 + 39 / 60,
    "Neptune": 3 + 41 / 60,
    "Pluto": 303.5330419654775,
}

# Base that the broad ladder proved solvable in Greek and Latin: all three
# exact W36 alignment groups + real Venus, with Uranus/Pluto kept easy.
W36_THREE_GROUPS_REAL_VENUS = {**W36_KNOWN_GOOD, "Uranus": 250, "Pluto": 300}

# Move Uranus around the short circular route from 250 degrees to its real
# 65.65-degree W36 longitude.  This finds the Greek/Latin search cliff.
W36_URANUS_LADDER = [
    ("uranus-250", {**W36_THREE_GROUPS_REAL_VENUS, "Uranus": 250}),
    ("uranus-280", {**W36_THREE_GROUPS_REAL_VENUS, "Uranus": 280}),
    ("uranus-310", {**W36_THREE_GROUPS_REAL_VENUS, "Uranus": 310}),
    ("uranus-340", {**W36_THREE_GROUPS_REAL_VENUS, "Uranus": 340}),
    ("uranus-010", {**W36_THREE_GROUPS_REAL_VENUS, "Uranus": 10}),
    ("uranus-030", {**W36_THREE_GROUPS_REAL_VENUS, "Uranus": 30}),
    ("uranus-045", {**W36_THREE_GROUPS_REAL_VENUS, "Uranus": 45}),
    ("uranus-055", {**W36_THREE_GROUPS_REAL_VENUS, "Uranus": 55}),
    ("uranus-060", {**W36_THREE_GROUPS_REAL_VENUS, "Uranus": 60}),
    ("uranus-real", {**W36_THREE_GROUPS_REAL_VENUS, "Uranus": W36_KNOWN_GOOD["Uranus"]}),
]

# Mixed failed as soon as all three exact W36 groups were present.  Hold the
# ordinary bodies easy and add the real groups pairwise before the triple.
MIXED_EASY = {
    "Venus": 210, "Uranus": 250, "Pluto": 300,
    "Sun": 50, "Mercury": 80, "Jupiter": 110,
    "Mars": 150, "Ceres": 180,
    "Neptune": 330, "Moon": 350, "Saturn": 20,
}

W36_MIXED_GROUP_LADDER = [
    ("mixed-one-NMS", {**MIXED_EASY,
        "Neptune": W36_KNOWN_GOOD["Neptune"], "Moon": W36_KNOWN_GOOD["Moon"],
        "Saturn": W36_KNOWN_GOOD["Saturn"]}),
    ("mixed-one-CM", {**MIXED_EASY,
        "Ceres": W36_KNOWN_GOOD["Ceres"], "Mars": W36_KNOWN_GOOD["Mars"]}),
    ("mixed-one-JSM", {**MIXED_EASY,
        "Jupiter": W36_KNOWN_GOOD["Jupiter"], "Sun": W36_KNOWN_GOOD["Sun"],
        "Mercury": W36_KNOWN_GOOD["Mercury"]}),
    ("mixed-two-NMS-CM", {**MIXED_EASY,
        "Neptune": W36_KNOWN_GOOD["Neptune"], "Moon": W36_KNOWN_GOOD["Moon"],
        "Saturn": W36_KNOWN_GOOD["Saturn"], "Ceres": W36_KNOWN_GOOD["Ceres"],
        "Mars": W36_KNOWN_GOOD["Mars"]}),
    ("mixed-two-NMS-JSM", {**MIXED_EASY,
        "Neptune": W36_KNOWN_GOOD["Neptune"], "Moon": W36_KNOWN_GOOD["Moon"],
        "Saturn": W36_KNOWN_GOOD["Saturn"], "Jupiter": W36_KNOWN_GOOD["Jupiter"],
        "Sun": W36_KNOWN_GOOD["Sun"], "Mercury": W36_KNOWN_GOOD["Mercury"]}),
    ("mixed-two-CM-JSM", {**MIXED_EASY,
        "Ceres": W36_KNOWN_GOOD["Ceres"], "Mars": W36_KNOWN_GOOD["Mars"],
        "Jupiter": W36_KNOWN_GOOD["Jupiter"], "Sun": W36_KNOWN_GOOD["Sun"],
        "Mercury": W36_KNOWN_GOOD["Mercury"]}),
    ("mixed-three-groups", {**W36_KNOWN_GOOD,
        "Venus": 210, "Uranus": 250, "Pluto": 300}),
]


def run_ladder(monkeypatch, week, mode, ladder, stop_on_failure=True):
    passed = []
    failures = []
    for level, longitudes in ladder:
        exact = level.startswith("exact-")
        seconds = REGRESSION_SECONDS if exact else LADDER_SECONDS
        monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")
        bodies = synthetic_bodies(longitudes)
        print(f"LADDER {week} {mode.value}: {level} START budget={seconds}s", flush=True)
        try:
            result = layout(
                mode, bodies, target_solutions=1,
                budget={"max_node_candidates": 2000, "max_seconds": seconds},
                context_label=f"ultimate-{week}-{level}-{mode.value}",
            )
            assert_complete_valid_layout(result, bodies, mode)
        except Exception as exc:
            failures.append((level, type(exc).__name__, str(exc)))
            print(f"LADDER {week} {mode.value}: {level} FAIL {type(exc).__name__}: {exc}", flush=True)
            if stop_on_failure:
                print(f"LADDER SUMMARY: week={week} mode={mode.value} passed={passed} FIRST_FAILURE={level}", flush=True)
                raise
        else:
            passed.append(level)
            print(f"LADDER {week} {mode.value}: {level} PASS", flush=True)
    print(f"LADDER SUMMARY: week={week} mode={mode.value} passed={passed} failures={failures}", flush=True)
    assert not failures, failures


@pytest.mark.parametrize("mode", [FinderMode.GREEK, FinderMode.LATIN])
def test_w36_uranus_breakpoint(monkeypatch, mode):
    run_ladder(monkeypatch, "W36-URANUS", mode, W36_URANUS_LADDER)


def test_w36_mixed_group_breakpoint(monkeypatch):
    # Pairwise cases are diagnostically independent, so run every rung even if
    # one fails; the final assertion reports the complete interaction map.
    run_ladder(monkeypatch, "W36-MIXED-GROUPS", FinderMode.MIXED,
               W36_MIXED_GROUP_LADDER, stop_on_failure=False)


@pytest.mark.parametrize("mode", MODES)
def test_exact_w36_regression(monkeypatch, mode):
    run_ladder(monkeypatch, "W36", mode, [("exact-W36", W36_KNOWN_GOOD)])


@pytest.mark.parametrize("mode", MODES)
def test_ultimate_w01_ladder(monkeypatch, mode):
    run_ladder(monkeypatch, "W01", mode, W01_LADDER)


@pytest.mark.parametrize("mode", MODES)
def test_ultimate_w02_ladder(monkeypatch, mode):
    run_ladder(monkeypatch, "W02", mode, W02_LADDER)
