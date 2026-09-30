"""Focused, self-checking W36 Planet Finder diagnostics plus W01/W02 ladders.

Every synthetic W36 rung asserts its alignment classification before layout is
allowed to run. Production solver code is untouched.
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

BASE_URANUS = {**W36_KNOWN_GOOD, "Uranus": 250, "Pluto": 300}

# Classification is asserted before layout.  The 250/55/60 fixtures have the
# three real W36 groups; once Uranus reaches 61 degrees it joins Ceres-Mars.
W36_URANUS_LADDER = [
    ("uranus-250", {**BASE_URANUS, "Uranus": 250},
     [("Neptune", "Moon", "Saturn"), ("Ceres", "Mars"), ("Jupiter", "Sun", "Mercury")]),
    ("uranus-055", {**BASE_URANUS, "Uranus": 55},
     [("Neptune", "Moon", "Saturn"), ("Ceres", "Mars"), ("Jupiter", "Sun", "Mercury")]),
    ("uranus-060", {**BASE_URANUS, "Uranus": 60},
     [("Neptune", "Moon", "Saturn"), ("Ceres", "Mars"), ("Jupiter", "Sun", "Mercury")]),
    ("uranus-061", {**BASE_URANUS, "Uranus": 61},
     [("Neptune", "Moon", "Saturn"), ("Uranus", "Ceres", "Mars"), ("Jupiter", "Sun", "Mercury")]),
    ("uranus-real", {**BASE_URANUS, "Uranus": W36_KNOWN_GOOD["Uranus"]},
     [("Neptune", "Moon", "Saturn"), ("Uranus", "Ceres", "Mars"), ("Jupiter", "Sun", "Mercury")]),
]

# Fast diagnostic sweep.  These are absolute Uranus longitudes, not angular
# separations.  The earlier 250-pass / 55-fail observation was easy to misread
# as 2.50 / 0.55 degrees.  Sweep the actual longitude while reporting whatever
# alignment classification each point really has.  Stop on the first layout
# failure so the Actions log gives us a small bracket instead of a 13-minute
# regression run.
W36_URANUS_SWEEP = [250, 220, 190, 160, 130, 110, 100, 90, 80, 70, 65, 62, 61, 60, 58, 55]

NMS = {"Neptune": W36_KNOWN_GOOD["Neptune"], "Moon": W36_KNOWN_GOOD["Moon"], "Saturn": W36_KNOWN_GOOD["Saturn"]}
CM = {"Ceres": W36_KNOWN_GOOD["Ceres"], "Mars": W36_KNOWN_GOOD["Mars"]}
JSM = {"Jupiter": W36_KNOWN_GOOD["Jupiter"], "Sun": W36_KNOWN_GOOD["Sun"], "Mercury": W36_KNOWN_GOOD["Mercury"]}


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
    placed = dict(active)
    for name in unused:
        found = None
        for lon in range(0, 360):
            trial = {**placed, name: float(lon)}
            bodies = [(n, n, x) for n, x in trial.items()]
            groups_now = alignment_groups(bodies)
            if all(all(item[1] in active for item in g) for g in groups_now):
                found = float(lon)
                break
        if found is None:
            raise AssertionError(f"cannot park {name} without contaminating {groups}")
        placed[name] = found
    return placed, sorted(expected)


def jsm_case(fraction):
    j = JSM["Jupiter"]
    exact_s = JSM["Sun"]
    exact_m = JSM["Mercury"]
    wide_s = j + 15.0
    wide_m = j + 29.0
    active = {
        "Jupiter": j,
        "Sun": wide_s + fraction * (exact_s - wide_s),
        "Mercury": wide_m + fraction * (exact_m - wide_m),
    }
    unused = [n for n in W36_KNOWN_GOOD if n not in active]
    placed = dict(active)
    for name in unused:
        found = None
        for lon in range(0, 360):
            trial = {**placed, name: float(lon)}
            bodies = [(n, n, x) for n, x in trial.items()]
            groups_now = alignment_groups(bodies)
            if all(all(item[1] in active for item in g) for g in groups_now):
                found = float(lon)
                break
        if found is None:
            raise AssertionError(f"cannot park {name} for JSM fraction {fraction}")
        placed[name] = found
    return placed, [("Jupiter", "Sun", "Mercury")]


W36_MIXED_JSM_LADDER = [
    ("jsm-wide", *jsm_case(0.0)),
    ("jsm-25pct", *jsm_case(0.25)),
    ("jsm-50pct", *jsm_case(0.50)),
    ("jsm-75pct", *jsm_case(0.75)),
    ("jsm-exact", *jsm_case(1.0)),
]


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


def test_00_fast_w36_venus_dead_end(monkeypatch):
    """Fast diagnostic: stop at the first exact-W36 Greek Uranus->Venus dead end."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    monkeypatch.setenv("PLANET_FINDER_FAST_VENUS_PROBE", "1")
    bodies = synthetic_bodies(W36_KNOWN_GOOD)
    with pytest.raises(RuntimeError, match="FAST_W36_VENUS_PROBE_COMPLETE"):
        layout(FinderMode.GREEK, bodies, target_solutions=1,
               budget={"max_node_candidates": 2000, "max_seconds": 15.0},
               context_label="fast-W36-Venus-probe")


def test_01_w36_uranus_longitude_sweep(monkeypatch):
    """Find the first Uranus longitude where the W36 layout stops solving."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    passed = []
    for longitude in W36_URANUS_SWEEP:
        longitudes = {**BASE_URANUS, "Uranus": float(longitude)}
        bodies = synthetic_bodies(longitudes)
        groups = group_names(bodies)
        print(f"URANUS SWEEP longitude={longitude:.1f} groups={groups} START", flush=True)
        try:
            result = layout(FinderMode.GREEK, bodies, target_solutions=1,
                            budget={"max_node_candidates": 2000, "max_seconds": 15.0},
                            context_label=f"W36-uranus-sweep-{longitude}")
            assert_complete_valid_layout(result, bodies, FinderMode.GREEK)
        except Exception as exc:
            previous = passed[-1] if passed else None
            print(
                f"URANUS SWEEP FIRST_FAILURE longitude={longitude:.1f} "
                f"previous_pass={previous} groups={groups} "
                f"error={type(exc).__name__}: {exc}",
                flush=True,
            )
            raise
        passed.append(longitude)
        print(f"URANUS SWEEP longitude={longitude:.1f} PASS", flush=True)
    print(f"URANUS SWEEP ALL_PASS={passed}", flush=True)


@pytest.mark.parametrize("mode", [FinderMode.GREEK, FinderMode.LATIN])
def test_w36_uranus_breakpoint(monkeypatch, mode):
    run_ladder(monkeypatch, "W36-URANUS", mode, W36_URANUS_LADDER)


def test_w36_mixed_jsm_breakpoint(monkeypatch):
    run_ladder(monkeypatch, "W36-MIXED-JSM", FinderMode.MIXED,
               W36_MIXED_JSM_LADDER, stop_on_failure=False)


@pytest.mark.parametrize("mode", MODES)
def test_exact_w36_regression(monkeypatch, mode):
    bodies = synthetic_bodies(W36_KNOWN_GOOD)
    expected = group_names(bodies)
    run_ladder(monkeypatch, "W36", mode, [("exact-W36", W36_KNOWN_GOOD, expected)])


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
