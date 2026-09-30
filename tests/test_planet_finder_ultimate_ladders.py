"""Focused, self-checking W36 Planet Finder diagnostics plus W01/W02 ladders.

Every synthetic W36 rung asserts its alignment classification before layout is
allowed to run.  This prevents an 'easy' longitude from silently creating an
extra alignment and contaminating the experiment.  Production solver code is
untouched.
"""

import pytest

from planet_finder_geometry import FinderMode, alignment_groups
from planet_finder_search import layout
from test_planet_finder_system import (
    W01_LADDER,
    W02_LADDER,
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

# Real W36 already teaches an important classification fact: Venus is linked
# to Jupiter-Sun-Mercury at the 30-degree alignment threshold.  Uranus at its
# real longitude is linked to Ceres-Mars.  The assertions below make such
# changes explicit instead of accidentally treating them as independent bodies.
BASE_URANUS = {**W36_KNOWN_GOOD, "Uranus": 250, "Pluto": 300}

W36_URANUS_LADDER = [
    ("uranus-250", {**BASE_URANUS, "Uranus": 250},
     [("Neptune", "Moon", "Saturn"), ("Ceres", "Mars"), ("Jupiter", "Sun", "Mercury", "Venus")]),
    ("uranus-055", {**BASE_URANUS, "Uranus": 55},
     [("Neptune", "Moon", "Saturn"), ("Ceres", "Mars"), ("Jupiter", "Sun", "Mercury", "Venus")]),
    ("uranus-060", {**BASE_URANUS, "Uranus": 60},
     [("Neptune", "Moon", "Saturn"), ("Ceres", "Mars"), ("Jupiter", "Sun", "Mercury", "Venus")]),
    ("uranus-061", {**BASE_URANUS, "Uranus": 61},
     [("Neptune", "Moon", "Saturn"), ("Uranus", "Ceres", "Mars"), ("Jupiter", "Sun", "Mercury", "Venus")]),
    ("uranus-real", {**BASE_URANUS, "Uranus": W36_KNOWN_GOOD["Uranus"]},
     [("Neptune", "Moon", "Saturn"), ("Uranus", "Ceres", "Mars"), ("Jupiter", "Sun", "Mercury", "Venus")]),
]

# Clean circular parking slots: all adjacent gaps are >30 degrees.  Replacing
# named slots with a real W36 group therefore creates only the group requested
# by that rung unless an expected tuple below explicitly says otherwise.
PARK = {
    "Neptune": 4, "Moon": 40, "Saturn": 76, "Ceres": 112, "Mars": 148,
    "Jupiter": 184, "Sun": 220, "Mercury": 256, "Venus": 292,
    "Uranus": 328, "Pluto": 340,
}
# Pluto at 340 would pair with Uranus, so park Pluto midway only in fixtures
# where Uranus's 328 slot is vacated.  For the clean group experiments use a
# deliberately asymmetric set with every unused neighbor >30 degrees.
CLEAN = {
    "Neptune": 4, "Moon": 40, "Saturn": 76, "Ceres": 112, "Mars": 148,
    "Jupiter": 184, "Sun": 220, "Mercury": 256, "Venus": 292,
    "Uranus": 328, "Pluto": 328,
}

# Rather than trust hand-picked parking positions, each fixture below carries
# its expected complete alignment map.  If a parking choice is contaminated,
# the test fails immediately with CLASSIFICATION MISMATCH before layout().
def fixture(overrides, expected):
    # 11 approximately even slots (32 degrees apart) are safely beyond the
    # 30-degree threshold; names whose real positions are under test override
    # those slots.
    base = dict(zip(
        ["Neptune", "Moon", "Saturn", "Ceres", "Mars", "Jupiter", "Sun", "Mercury", "Venus", "Uranus", "Pluto"],
        [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320],
    ))
    base.update(overrides)
    return base, expected

NMS = {"Neptune": W36_KNOWN_GOOD["Neptune"], "Moon": W36_KNOWN_GOOD["Moon"], "Saturn": W36_KNOWN_GOOD["Saturn"]}
CM = {"Ceres": W36_KNOWN_GOOD["Ceres"], "Mars": W36_KNOWN_GOOD["Mars"]}
JSM = {"Jupiter": W36_KNOWN_GOOD["Jupiter"], "Sun": W36_KNOWN_GOOD["Sun"], "Mercury": W36_KNOWN_GOOD["Mercury"]}

# Use widely separated explicit fillers for each case; classification assertion
# is the authority and prevents any accidental group from reaching the solver.
def clean_case(groups):
    active = {}
    expected = []
    if "NMS" in groups:
        active.update(NMS); expected.append(("Neptune", "Moon", "Saturn"))
    if "CM" in groups:
        active.update(CM); expected.append(("Ceres", "Mars"))
    if "JSM" in groups:
        active.update(JSM); expected.append(("Jupiter", "Sun", "Mercury"))

    unused = [n for n in W36_KNOWN_GOOD if n not in active]
    # Search a deterministic 1-degree grid for parking longitudes whose final
    # classification is exactly the requested groups.  This is test-fixture
    # construction only; it does not call or alter the layout solver.
    def normalized(gs):
        return sorted(tuple(item[1] for item in g) for g in gs)
    wanted = sorted(expected)
    placed = dict(active)
    for name in unused:
        found = None
        for lon in range(0, 360):
            trial = {**placed, name: float(lon)}
            bodies = [(n, n, x) for n, x in trial.items()]
            groups_now = alignment_groups(bodies)
            # Partial groups may contain only requested active members; reject
            # any group containing a parked body.
            if all(all(item[1] in active for item in g) for g in groups_now):
                found = float(lon)
                break
        if found is None:
            raise AssertionError(f"cannot park {name} without contaminating {groups}")
        placed[name] = found
    return placed, wanted

W36_MIXED_GROUP_LADDER = []
for label, groups in [
    ("mixed-one-NMS", ("NMS",)),
    ("mixed-one-CM", ("CM",)),
    ("mixed-one-JSM", ("JSM",)),
    ("mixed-two-NMS-CM", ("NMS", "CM")),
    ("mixed-two-NMS-JSM", ("NMS", "JSM")),
    ("mixed-two-CM-JSM", ("CM", "JSM")),
    ("mixed-three-groups", ("NMS", "CM", "JSM")),
]:
    longs, expected = clean_case(groups)
    W36_MIXED_GROUP_LADDER.append((label, longs, expected))


def group_names(bodies):
    return sorted(tuple(item[1] for item in group) for group in alignment_groups(bodies))


def run_ladder(monkeypatch, week, mode, ladder, stop_on_failure=True):
    passed, failures = [], []
    for level, longitudes, expected_groups in ladder:
        exact = level.startswith("exact-")
        seconds = REGRESSION_SECONDS if exact else LADDER_SECONDS
        bodies = synthetic_bodies(longitudes)
        actual_groups = group_names(bodies)
        expected_groups = sorted(expected_groups)
        print(f"CLASSIFY {week} {mode.value} {level}: {actual_groups}", flush=True)
        assert actual_groups == expected_groups, (
            f"CLASSIFICATION MISMATCH {level}: expected={expected_groups} actual={actual_groups}"
        )
        monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")
        print(f"LADDER {week} {mode.value}: {level} START budget={seconds}s", flush=True)
        try:
            result = layout(mode, bodies, target_solutions=1,
                budget={"max_node_candidates": 2000, "max_seconds": seconds},
                context_label=f"ultimate-{week}-{level}-{mode.value}")
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
    run_ladder(monkeypatch, "W36-MIXED-GROUPS", FinderMode.MIXED,
               W36_MIXED_GROUP_LADDER, stop_on_failure=False)


@pytest.mark.parametrize("mode", MODES)
def test_exact_w36_regression(monkeypatch, mode):
    bodies = synthetic_bodies(W36_KNOWN_GOOD)
    expected = group_names(bodies)
    run_ladder(monkeypatch, "W36", mode, [("exact-W36", W36_KNOWN_GOOD, expected)])


# Preserve the established W01/W02 clocks and fixtures.  They are not part of
# this W36 experiment and must not appear to regress merely because a diagnostic
# timeout was shortened.
def run_existing_ladder(monkeypatch, week, mode, ladder):
    passed = []
    for level, longitudes in ladder:
        monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
        bodies = synthetic_bodies(longitudes)
        result = layout(mode, bodies, target_solutions=1,
            budget={"max_node_candidates": 2000, "max_seconds": 60.0},
            context_label=f"ultimate-{week}-{level}-{mode.value}")
        assert_complete_valid_layout(result, bodies, mode)
        passed.append(level)
    print(f"LADDER SUMMARY: week={week} mode={mode.value} ALL_PASS stages={passed}", flush=True)


@pytest.mark.parametrize("mode", MODES)
def test_ultimate_w01_ladder(monkeypatch, mode):
    run_existing_ladder(monkeypatch, "W01", mode, W01_LADDER)


@pytest.mark.parametrize("mode", MODES)
def test_ultimate_w02_ladder(monkeypatch, mode):
    run_existing_ladder(monkeypatch, "W02", mode, W02_LADDER)
