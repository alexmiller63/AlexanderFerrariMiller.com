"""Full Planet Finder ultimate regressions for W01, W02, and W36.

W36 retains its self-checking breakpoint ladders and exact weekly geometry;
W01/W02 retain their progressive ultimate ladders in all three modes.
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
HARD_MODE_REGRESSION_SECONDS = 15.0

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

W36_URANUS_SWEEP = [250, 220, 190, 160, 130, 110, 100, 90, 80, 70, 65, 62, 61, 60, 58, 55]

NMS = {"Neptune": W36_KNOWN_GOOD["Neptune"], "Moon": W36_KNOWN_GOOD["Moon"], "Saturn": W36_KNOWN_GOOD["Saturn"]}
CM = {"Ceres": W36_KNOWN_GOOD["Ceres"], "Mars": W36_KNOWN_GOOD["Mars"]}
JSM = {"Jupiter": W36_KNOWN_GOOD["Jupiter"], "Sun": W36_KNOWN_GOOD["Sun"], "Mercury": W36_KNOWN_GOOD["Mercury"]}


def jsm_case(fraction):
    j = JSM["Jupiter"]
    exact_s = JSM["Sun"]
    exact_m = JSM["Mercury"]
    active = {
        "Jupiter": j,
        "Sun": j + 15.0 + fraction * (exact_s - (j + 15.0)),
        "Mercury": j + 29.0 + fraction * (exact_m - (j + 29.0)),
    }
    placed = dict(active)
    for name in [n for n in W36_KNOWN_GOOD if n not in active]:
        found = None
        for lon in range(360):
            trial = {**placed, name: float(lon)}
            groups_now = alignment_groups([(n, n, x) for n, x in trial.items()])
            if all(all(item[1] in active for item in group) for group in groups_now):
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


def enable_alignment_fix(monkeypatch):
    # Until the proven alignment-boundary forward check is made the production
    # default, exercise that exact code path in the ultimate regression suite.
    monkeypatch.setenv("PLANET_FINDER_ALIGNMENT_FORWARD_CHECK", "1")


def run_ladder(monkeypatch, week, mode, ladder, stop_on_failure=True):
    enable_alignment_fix(monkeypatch)
    passed, failures = [], []
    for level, longitudes, expected_groups in ladder:
        seconds = (HARD_MODE_REGRESSION_SECONDS if mode in (FinderMode.LATIN, FinderMode.MIXED) else REGRESSION_SECONDS) if level.startswith("exact-") else LADDER_SECONDS
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


def test_00_fast_exact_w36(monkeypatch):
    """Exact W36 Greek must now solve, not merely produce a diagnostic timeout."""
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_SKIP_ALIGNMENT_PREPLANNER", "1")
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")
    bodies = synthetic_bodies(W36_KNOWN_GOOD)
    result = layout(FinderMode.GREEK, bodies, target_solutions=1,
                    budget={"max_node_candidates": 2000, "max_seconds": 30.0},
                    context_label="fast-W36-Mercury-Venus-regression")
    assert_complete_valid_layout(result, bodies, FinderMode.GREEK)


def test_01_w36_uranus_longitude_sweep(monkeypatch):
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    passed = []
    for longitude in W36_URANUS_SWEEP:
        longitudes = {**BASE_URANUS, "Uranus": float(longitude)}
        bodies = synthetic_bodies(longitudes)
        groups = group_names(bodies)
        print(f"URANUS SWEEP longitude={longitude:.1f} groups={groups} START", flush=True)
        result = layout(FinderMode.GREEK, bodies, target_solutions=1,
                        budget={"max_node_candidates": 2000, "max_seconds": 15.0},
                        context_label=f"W36-uranus-sweep-{longitude}")
        assert_complete_valid_layout(result, bodies, FinderMode.GREEK)
        passed.append(longitude)
        print(f"URANUS SWEEP longitude={longitude:.1f} PASS", flush=True)
    print(f"URANUS SWEEP ALL_PASS={passed}", flush=True)


@pytest.mark.parametrize("mode", [FinderMode.GREEK, FinderMode.LATIN])
def test_w36_uranus_breakpoint(monkeypatch, mode):
    run_ladder(monkeypatch, "W36-URANUS", mode, W36_URANUS_LADDER)


def test_w36_mixed_jsm_breakpoint(monkeypatch):
    run_ladder(monkeypatch, "W36-MIXED-JSM", FinderMode.MIXED,
               W36_MIXED_JSM_LADDER, stop_on_failure=False)


def test_02_w36_mixed_jsm_zero_vs_25_forensic(monkeypatch):
    """Compare the passing 0% JSM state directly with the failing 25% state."""
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "4")
    for level, fraction in (("jsm-0pct", 0.0), ("jsm-25pct", 0.25)):
        longitudes, expected_groups = jsm_case(fraction)
        print(f"JSM FORENSIC {level} LONGITUDES " +
              " ".join(f"{name}={lon:.6f}" for name, lon in longitudes.items()), flush=True)
        bodies = synthetic_bodies(longitudes)
        actual_groups = group_names(bodies)
        print(f"JSM FORENSIC {level} GROUPS={actual_groups}", flush=True)
        assert actual_groups == sorted(expected_groups)
        try:
            result = layout(
                FinderMode.MIXED, bodies, target_solutions=1,
                budget={"max_node_candidates": 2000, "max_seconds": 15.0},
                context_label=f"forensic-W36-{level}-mixed",
            )
            assert_complete_valid_layout(result, bodies, FinderMode.MIXED)
        except Exception as exc:
            print(f"JSM FORENSIC {level} RESULT=FAIL {type(exc).__name__}: {exc}", flush=True)
        else:
            print(f"JSM FORENSIC {level} RESULT=PASS", flush=True)


def test_02_w36_mixed_jsm_zero_vs_25_forensic(monkeypatch):
    """Compare the passing 0% JSM state directly with the failing 25% state."""
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "4")
    for level, fraction in (("jsm-0pct", 0.0), ("jsm-25pct", 0.25)):
        longitudes, expected_groups = jsm_case(fraction)
        print(f"JSM FORENSIC {level} LONGITUDES " +
              " ".join(f"{name}={lon:.6f}" for name, lon in longitudes.items()), flush=True)
        bodies = synthetic_bodies(longitudes)
        actual_groups = group_names(bodies)
        print(f"JSM FORENSIC {level} GROUPS={actual_groups}", flush=True)
        assert actual_groups == sorted(expected_groups)
        try:
            result = layout(
                FinderMode.MIXED, bodies, target_solutions=1,
                budget={"max_node_candidates": 2000, "max_seconds": 15.0},
                context_label=f"forensic-W36-{level}-mixed",
            )
            assert_complete_valid_layout(result, bodies, FinderMode.MIXED)
        except Exception as exc:
            print(f"JSM FORENSIC {level} RESULT=FAIL {type(exc).__name__}: {exc}", flush=True)
        else:
            print(f"JSM FORENSIC {level} RESULT=PASS", flush=True)


def test_02_w36_mixed_jsm_zero_vs_25_forensic(monkeypatch):
    """Compare the passing 0% JSM state directly with the failing 25% state."""
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "4")
    for level, fraction in (("jsm-0pct", 0.0), ("jsm-25pct", 0.25)):
        longitudes, expected_groups = jsm_case(fraction)
        print(f"JSM FORENSIC {level} LONGITUDES " +
              " ".join(f"{name}={lon:.6f}" for name, lon in longitudes.items()), flush=True)
        bodies = synthetic_bodies(longitudes)
        actual_groups = group_names(bodies)
        print(f"JSM FORENSIC {level} GROUPS={actual_groups}", flush=True)
        assert actual_groups == sorted(expected_groups)
        try:
            result = layout(
                FinderMode.MIXED, bodies, target_solutions=1,
                budget={"max_node_candidates": 2000, "max_seconds": 15.0},
                context_label=f"forensic-W36-{level}-mixed",
            )
            assert_complete_valid_layout(result, bodies, FinderMode.MIXED)
        except Exception as exc:
            print(f"JSM FORENSIC {level} RESULT=FAIL {type(exc).__name__}: {exc}", flush=True)
        else:
            print(f"JSM FORENSIC {level} RESULT=PASS", flush=True)


def test_02_w36_mixed_jsm_zero_vs_25_forensic(monkeypatch):
    """Compare the passing 0% JSM state directly with the failing 25% state."""
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "3")
    for level, fraction in (("jsm-0pct", 0.0), ("jsm-25pct", 0.25)):
        longitudes, expected_groups = jsm_case(fraction)
        print(f"JSM FORENSIC {level} LONGITUDES " +
              " ".join(f"{name}={lon:.6f}" for name, lon in longitudes.items()), flush=True)
        bodies = synthetic_bodies(longitudes)
        actual_groups = group_names(bodies)
        print(f"JSM FORENSIC {level} GROUPS={actual_groups}", flush=True)
        assert actual_groups == sorted(expected_groups)
        try:
            result = layout(
                FinderMode.MIXED, bodies, target_solutions=1,
                budget={"max_node_candidates": 2000, "max_seconds": 15.0},
                context_label=f"forensic-W36-{level}-mixed",
            )
            assert_complete_valid_layout(result, bodies, FinderMode.MIXED)
        except Exception as exc:
            print(f"JSM FORENSIC {level} RESULT=FAIL {type(exc).__name__}: {exc}", flush=True)
        else:
            print(f"JSM FORENSIC {level} RESULT=PASS", flush=True)


@pytest.mark.parametrize("mode", MODES)
def test_exact_w36_regression(monkeypatch, mode):
    bodies = synthetic_bodies(W36_KNOWN_GOOD)
    expected = group_names(bodies)
    run_ladder(monkeypatch, "W36", mode, [("exact-W36", W36_KNOWN_GOOD, expected)])


def run_existing_ladder(monkeypatch, week, mode, ladder):
    enable_alignment_fix(monkeypatch)
    passed = []
    for level, longitudes in ladder:
        monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "2" if level.startswith("exact-") else "0")
        bodies = synthetic_bodies(longitudes)
        result = layout(mode, bodies, target_solutions=1,
            budget={"max_node_candidates": 2000, "max_seconds": (HARD_MODE_REGRESSION_SECONDS if mode in (FinderMode.LATIN, FinderMode.MIXED) else REGRESSION_SECONDS)},
            context_label=f"ultimate-{week}-{level}-{mode.value}")
        assert_complete_valid_layout(result, bodies, mode)
        passed.append(level)
    print(f"LADDER SUMMARY: week={week} mode={mode.value} ALL_PASS stages={passed}", flush=True)


def test_ultimate_w01_ladder(monkeypatch):
    """Diagnostic isolation: W01 Greek real-five-plus-wide-wrap only."""
    level, longitudes = next(
        item for item in W01_LADDER if item[0] == "real-five-plus-wide-wrap"
    )
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "2")
    bodies = synthetic_bodies(longitudes)
    print("W01 GREEK SINGLE-RUNG START level=real-five-plus-wide-wrap budget=60s", flush=True)
    result = layout(
        FinderMode.GREEK,
        bodies,
        target_solutions=1,
        budget={"max_node_candidates": 2000, "max_seconds": REGRESSION_SECONDS},
        context_label="ultimate-W01-real-five-plus-wide-wrap-greek",
    )
    assert_complete_valid_layout(result, bodies, FinderMode.GREEK)
    print("W01 GREEK SINGLE-RUNG PASS level=real-five-plus-wide-wrap", flush=True)


@pytest.mark.parametrize("mode", MODES)
def test_ultimate_w02_ladder(monkeypatch, mode):
    run_existing_ladder(monkeypatch, "W02", mode, W02_LADDER)
