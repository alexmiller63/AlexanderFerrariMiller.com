"""Progressive W36/W01/W02 Planet Finder diagnostic ladders.

W36 is the hard-won production baseline.  Its ladder isolates the point where
current alignment handling diverges from that known-good geometry.  Exact W36,
W01 and W02 remain immutable endpoints.  Production solver code is untouched.
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

# Frozen 2026-W36 production geometry.  Keep this fixture independent of
# Skyfield kernels: its purpose is to catch Planet Finder regressions, not to
# retest ephemeris generation.
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

# Simple -> exact W36.  Each stage adds one piece of the real W36 geometry so
# the first timeout identifies the interaction that causes the search cliff.
W36_LADDER = [
    ("separated", {
        "Sun": 0, "Mercury": 35, "Venus": 70, "Mars": 105, "Ceres": 140,
        "Jupiter": 175, "Saturn": 210, "Moon": 245, "Neptune": 280,
        "Uranus": 315, "Pluto": 335,
    }),
    ("neptune-moon-saturn-wide", {
        "Neptune": 350, "Moon": 5, "Saturn": 20,
        "Sun": 50, "Mercury": 80, "Venus": 110, "Mars": 140,
        "Ceres": 170, "Jupiter": 200, "Uranus": 240, "Pluto": 290,
    }),
    ("neptune-moon-saturn-exact", {
        "Neptune": W36_KNOWN_GOOD["Neptune"], "Moon": W36_KNOWN_GOOD["Moon"],
        "Saturn": W36_KNOWN_GOOD["Saturn"],
        "Sun": 50, "Mercury": 80, "Venus": 110, "Mars": 140,
        "Ceres": 170, "Jupiter": 200, "Uranus": 240, "Pluto": 290,
    }),
    ("plus-ceres-mars-wide", {
        "Neptune": W36_KNOWN_GOOD["Neptune"], "Moon": W36_KNOWN_GOOD["Moon"],
        "Saturn": W36_KNOWN_GOOD["Saturn"], "Ceres": 90, "Mars": 105,
        "Sun": 50, "Mercury": 70, "Venus": 140, "Jupiter": 180,
        "Uranus": 230, "Pluto": 290,
    }),
    ("plus-ceres-mars-exact", {
        "Neptune": W36_KNOWN_GOOD["Neptune"], "Moon": W36_KNOWN_GOOD["Moon"],
        "Saturn": W36_KNOWN_GOOD["Saturn"], "Ceres": W36_KNOWN_GOOD["Ceres"],
        "Mars": W36_KNOWN_GOOD["Mars"],
        "Sun": 50, "Mercury": 70, "Venus": 140, "Jupiter": 180,
        "Uranus": 230, "Pluto": 290,
    }),
    ("plus-jupiter-sun-mercury-wide", {
        "Neptune": W36_KNOWN_GOOD["Neptune"], "Moon": W36_KNOWN_GOOD["Moon"],
        "Saturn": W36_KNOWN_GOOD["Saturn"], "Ceres": W36_KNOWN_GOOD["Ceres"],
        "Mars": W36_KNOWN_GOOD["Mars"], "Jupiter": 130, "Sun": 150,
        "Mercury": 170, "Venus": 220, "Uranus": 260, "Pluto": 300,
    }),
    ("all-three-groups-easy-others", {
        "Neptune": W36_KNOWN_GOOD["Neptune"], "Moon": W36_KNOWN_GOOD["Moon"],
        "Saturn": W36_KNOWN_GOOD["Saturn"], "Ceres": W36_KNOWN_GOOD["Ceres"],
        "Mars": W36_KNOWN_GOOD["Mars"], "Jupiter": W36_KNOWN_GOOD["Jupiter"],
        "Sun": W36_KNOWN_GOOD["Sun"], "Mercury": W36_KNOWN_GOOD["Mercury"],
        "Venus": 210, "Uranus": 250, "Pluto": 300,
    }),
    ("all-groups-plus-real-venus", {
        **W36_KNOWN_GOOD, "Uranus": 250, "Pluto": 300,
    }),
    ("all-groups-plus-real-venus-uranus", {
        **W36_KNOWN_GOOD, "Pluto": 300,
    }),
    ("exact-W36", W36_KNOWN_GOOD),
]


def run_ladder(monkeypatch, week, mode, ladder):
    passed = []
    for level, longitudes in ladder:
        exact = level.startswith("exact-")
        seconds = REGRESSION_SECONDS if exact else LADDER_SECONDS
        monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "2" if exact else "1")
        bodies = synthetic_bodies(longitudes)
        print(f"LADDER {week} {mode.value}: {level} START budget={seconds}s", flush=True)
        try:
            result = layout(
                mode,
                bodies,
                target_solutions=1,
                budget={"max_node_candidates": 2000, "max_seconds": seconds},
                context_label=f"ultimate-{week}-{level}-{mode.value}",
            )
            assert_complete_valid_layout(result, bodies, mode)
            if (
                mode != FinderMode.GREEK
                and level in {
                    "exact-W36", "both-real-alignments", "exact-W01",
                    "all-W02-groups", "exact-W02",
                }
            ):
                assert_alignment_labels_follow_lambda(result, bodies)
        except Exception as exc:
            print(
                f"LADDER SUMMARY: week={week} mode={mode.value} "
                f"passed={passed} FIRST_FAILURE={level} "
                f"budget={seconds}s error={type(exc).__name__}: {exc}",
                flush=True,
            )
            raise
        passed.append(level)
        print(f"LADDER {week} {mode.value}: {level} PASS", flush=True)

    print(
        f"LADDER SUMMARY: week={week} mode={mode.value} "
        f"ALL_PASS stages={passed}",
        flush=True,
    )


@pytest.mark.parametrize("mode", MODES)
def test_ultimate_w36_ladder(monkeypatch, mode):
    run_ladder(monkeypatch, "W36", mode, W36_LADDER)


@pytest.mark.parametrize("mode", MODES)
def test_ultimate_w01_ladder(monkeypatch, mode):
    run_ladder(monkeypatch, "W01", mode, W01_LADDER)


@pytest.mark.parametrize("mode", MODES)
def test_ultimate_w02_ladder(monkeypatch, mode):
    run_ladder(monkeypatch, "W02", mode, W02_LADDER)
