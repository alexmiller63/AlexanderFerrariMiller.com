"""Full Planet Finder ultimate regressions for W01, W02, and W36.

W36 retains its self-checking breakpoint ladders and exact weekly geometry;
W01/W02 retain their progressive ultimate ladders in all three modes.
"""

import time

import pytest

from planet_finder_geometry import FinderMode, alignment_groups
from planet_finder_search import layout
from planet_finder_search_core import _solve_order
from test_planet_finder_system import (
    W01_LADDER,
    W02_LADDER,
    TIGHT_FIVE_LADDER,
    assert_complete_valid_layout,
    synthetic_bodies,
)

MODES = [FinderMode.GREEK, FinderMode.LATIN, FinderMode.MIXED]
LADDER_SECONDS = 15.0
REGRESSION_SECONDS = 60.0
HARD_MODE_REGRESSION_SECONDS = 120.0

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
    # Preserve the forensic's widest Uranus/Jupiter geometry while allowing
    # fail-first selection among every remaining recursive body.
    monkeypatch.setenv("PLANET_FINDER_DFS_FIXED_PREFIX", "2")
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


def test_w36_latin_progressive_alignment_ladder(monkeypatch):
    """Approach exact W36 Latin from isolated, solvable alignment geometry."""
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")

    stages = []
    for label, fraction in (
        ("jsm-wide", 0.0),
        ("jsm-25pct", 0.25),
        ("jsm-50pct", 0.50),
        ("jsm-75pct", 0.75),
        ("jsm-exact-isolated", 1.0),
    ):
        longitudes, expected_groups = jsm_case(fraction)
        stages.append((label, longitudes, expected_groups, 15.0))

    # Then restore the other real W36 alignment interactions one group at a
    # time while keeping the real JSM geometry. This identifies the first
    # interaction that turns the isolated Latin case pathological.
    isolated_exact, _ = jsm_case(1.0)
    stages.extend([
        (
            "plus-saturn-ceres-mars",
            {**isolated_exact, **CM},
            [("Saturn", "Ceres", "Mars"), ("Jupiter", "Sun", "Mercury")],
            20.0,
        ),
        (
            "restore-real-neptune-moon-saturn",
            {**isolated_exact, **CM, **NMS},
            [
                ("Neptune", "Moon", "Saturn", "Venus"),
                ("Ceres", "Mars"),
                ("Jupiter", "Sun", "Mercury"),
            ],
            30.0,
        ),
        # Split the last jump into ordinary-body deltas. The previous
        # rung already restores all real W36 alignment interactions; these
        # stages identify the smallest remaining real longitude that makes
        # Latin pathological.
        (
            "plus-real-uranus",
            {**isolated_exact, **CM, **NMS, "Uranus": W36_KNOWN_GOOD["Uranus"]},
            group_names(synthetic_bodies({**isolated_exact, **CM, **NMS, "Uranus": W36_KNOWN_GOOD["Uranus"]})),
            30.0,
        ),
        (
            "plus-real-pluto",
            {**isolated_exact, **CM, **NMS, "Pluto": W36_KNOWN_GOOD["Pluto"]},
            group_names(synthetic_bodies({**isolated_exact, **CM, **NMS, "Pluto": W36_KNOWN_GOOD["Pluto"]})),
            30.0,
        ),
        (
            "plus-real-venus",
            {**isolated_exact, **CM, **NMS, "Venus": W36_KNOWN_GOOD["Venus"]},
            group_names(synthetic_bodies({**isolated_exact, **CM, **NMS, "Venus": W36_KNOWN_GOOD["Venus"]})),
            30.0,
        ),
        (
            "plus-real-uranus-pluto",
            {**isolated_exact, **CM, **NMS, "Uranus": W36_KNOWN_GOOD["Uranus"], "Pluto": W36_KNOWN_GOOD["Pluto"]},
            group_names(synthetic_bodies({**isolated_exact, **CM, **NMS, "Uranus": W36_KNOWN_GOOD["Uranus"], "Pluto": W36_KNOWN_GOOD["Pluto"]})),
            45.0,
        ),
        (
            "plus-real-uranus-venus",
            {**isolated_exact, **CM, **NMS, "Uranus": W36_KNOWN_GOOD["Uranus"], "Venus": W36_KNOWN_GOOD["Venus"]},
            group_names(synthetic_bodies({**isolated_exact, **CM, **NMS, "Uranus": W36_KNOWN_GOOD["Uranus"], "Venus": W36_KNOWN_GOOD["Venus"]})),
            45.0,
        ),
        (
            "plus-real-pluto-venus",
            {**isolated_exact, **CM, **NMS, "Pluto": W36_KNOWN_GOOD["Pluto"], "Venus": W36_KNOWN_GOOD["Venus"]},
            group_names(synthetic_bodies({**isolated_exact, **CM, **NMS, "Pluto": W36_KNOWN_GOOD["Pluto"], "Venus": W36_KNOWN_GOOD["Venus"]})),
            45.0,
        ),
        (
            "exact-W36",
            W36_KNOWN_GOOD,
            group_names(synthetic_bodies(W36_KNOWN_GOOD)),
            HARD_MODE_REGRESSION_SECONDS,
        ),
    ])

    passed = []
    for label, longitudes, expected_groups, seconds in stages:
        bodies = synthetic_bodies(longitudes)
        actual_groups = group_names(bodies)
        expected_groups = sorted(expected_groups)
        print(
            f"LATIN PROGRESSIVE {label}: groups={actual_groups} budget={seconds}s START",
            flush=True,
        )
        assert actual_groups == expected_groups, (
            f"CLASSIFICATION MISMATCH {label}: expected={expected_groups} actual={actual_groups}"
        )
        result = layout(
            FinderMode.LATIN,
            bodies,
            target_solutions=1,
            budget={"max_node_candidates": 2000, "max_seconds": seconds},
            context_label=f"W36-latin-progressive-{label}",
        )
        assert_complete_valid_layout(result, bodies, FinderMode.LATIN)
        passed.append(label)
        print(f"LATIN PROGRESSIVE {label}: PASS", flush=True)

    print(f"LATIN PROGRESSIVE SUMMARY passed={passed}", flush=True)


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


def test_w01_wide_wrap_greek_forensic(monkeypatch):
    """Compare both recursive orders at the first failing W01 ladder boundary."""
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "4")
    # For this forensic, bypass the entire coordinated alignment layer so the
    # full budget observes ordinary recursive DFS/backtracking under the
    # wide-wrap astronomical configuration.
    monkeypatch.setenv("PLANET_FINDER_SKIP_ALIGNMENT_PREPLANNER", "1")

    level, longitudes = next(
        item for item in W01_LADDER if item[0] == "real-five-plus-wide-wrap"
    )
    bodies = synthetic_bodies(longitudes)
    print(
        "W01 WIDE-WRAP FORENSIC groups="
        + repr(group_names(bodies)),
        flush=True,
    )

    by_name = {
        name: (index, body)
        for index, body in enumerate(bodies)
        for name in (body[1],)
    }
    # Geometric invariant under test: the wide-wrap pair is already the
    # maximum-separation geometry. Do not narrow it as a fallback. Instead,
    # keep that geometry fixed and prove that ordinary DFS backtracks through
    # the remaining bodies around it.
    pair = [by_name["Uranus"], by_name["Jupiter"]]
    remaining = [
        (index, body) for index, body in enumerate(bodies)
        if body[1] not in {"Uranus", "Jupiter"}
    ]
    orders = [
        ("WIDEST-FIXED-URANUS-FIRST", pair + remaining),
        ("WIDEST-FIXED-JUPITER-FIRST", list(reversed(pair)) + remaining),
    ]

    results = {}
    for label, order in orders:
        budget = {
            "max_node_candidates": 2000,
            "max_seconds": REGRESSION_SECONDS,
            "started": time.monotonic(),
        }
        deadline = budget["started"] + budget["max_seconds"]
        body_attempts = {body[1]: 0 for _, body in order}
        print(
            f"W01 ORDER FORENSIC {label} START sequence="
            + " > ".join(item[1][1] for item in order),
            flush=True,
        )
        # The first two bodies are the fixed widest Uranus/Jupiter geometry.
        # Exercise the same squeaky-wheel promotion contract as layout(): a
        # repeated forward blocker may move left among the remaining recursive
        # bodies, but it must never displace or narrow the fixed pair.
        fixed_prefix = 2
        attempted_orders = set()
        attempt = 0
        while True:
            attempt += 1
            order_names = tuple(item[1][1] for item in order)
            if order_names in attempted_orders:
                raise AssertionError(
                    f"{label} promotion cycle: " + " > ".join(order_names)
                )
            attempted_orders.add(order_names)
            outcome = _solve_order(
                FinderMode.GREEK,
                bodies,
                order,
                budget,
                target_solutions=1,
                order_index=attempt,
                total_orders=None,
                context_label=f"forensic-W01-{label.lower()}",
                displacement_scale=0.25,
                body_attempts=body_attempts,
                refinement_deadline=deadline,
            )
            if outcome.solutions or outcome.kind not in ("CAPPED", "EXHAUSTED") or not outcome.blocker:
                break

            blocker_index = next(
                (i for i, item in enumerate(order) if item[1][1] == outcome.blocker),
                None,
            )
            if blocker_index is None or blocker_index <= fixed_prefix:
                break

            # Promote past as many neighbors as necessary to reach the nearest
            # ordering we have not already searched.  A single adjacent swap
            # can oscillate (for example Neptune <-> Saturn); that is search
            # history, not new geometric information.
            promoted = None
            for target_index in range(blocker_index - 1, fixed_prefix - 1, -1):
                candidate = list(order)
                blocker_item = candidate.pop(blocker_index)
                candidate.insert(target_index, blocker_item)
                candidate_names = tuple(item[1][1] for item in candidate)
                if candidate_names not in attempted_orders:
                    promoted = candidate
                    break
            if promoted is None:
                break

            print(
                f"W01 ORDER FORENSIC {label} PROMOTE body={outcome.blocker} "
                f"attempt={attempt} sequence="
                + " > ".join(item[1][1] for item in promoted),
                flush=True,
            )
            order = promoted
            body_attempts[outcome.blocker] = 0

        results[label] = outcome
        print(
            f"W01 ORDER FORENSIC {label} RESULT kind={outcome.kind} "
            f"blocker={outcome.blocker} solutions={len(outcome.solutions)} "
            f"attempts={body_attempts}",
            flush=True,
        )
        if outcome.solutions:
            assert_complete_valid_layout(
                outcome.solutions[0], bodies, FinderMode.GREEK
            )

    assert any(outcome.solutions for outcome in results.values()), (
        "Neither Uranus-first nor Jupiter-first produced a complete layout: "
        + repr({
            label: (outcome.kind, outcome.blocker)
            for label, outcome in results.items()
        })
    )


@pytest.mark.parametrize("mode", MODES)
def test_ultimate_w01_ladder(monkeypatch, mode):
    run_existing_ladder(monkeypatch, "W01", mode, W01_LADDER)


@pytest.mark.parametrize("mode", MODES)
def test_ultimate_w02_ladder(monkeypatch, mode):
    run_existing_ladder(monkeypatch, "W02", mode, W02_LADDER)


@pytest.mark.parametrize("week,ladder", [
    ("W01", W01_LADDER),
    ("W02", W02_LADDER),
])
def test_five_candidate_exact_w01_w02_regression(monkeypatch, week, ladder):
    """Exact W01/W02 Greek regression using the production five-candidate target."""
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")
    level, longitudes = ladder[-1]
    bodies = synthetic_bodies(longitudes)
    print(f"FIVE-CANDIDATE REGRESSION {week} {level} START", flush=True)
    result = layout(
        FinderMode.GREEK,
        bodies,
        target_solutions=5,
        budget={"max_node_candidates": 2000, "max_seconds": 120.0},
        context_label=f"five-candidate-regression-{week}",
    )
    assert_complete_valid_layout(result, bodies, FinderMode.GREEK)
    print(f"FIVE-CANDIDATE REGRESSION {week} {level} PASS", flush=True)




def test_w01_tight_alignment_size_ladder(monkeypatch):
    """Isolate the complexity jump as the real W01 inner alignment grows to five members."""
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")

    exact = W01_LADDER[-1][1]
    isolated = {"Saturn": 20, "Neptune": 60, "Ceres": 100, "Moon": 140, "Uranus": 180, "Jupiter": 220}
    stages = [
        ("tight-2", {"Venus", "Sun"}),
        ("tight-3", {"Venus", "Sun", "Mars"}),
        ("tight-4", {"Mercury", "Venus", "Sun", "Mars"}),
        ("tight-5", {"Mercury", "Venus", "Sun", "Mars", "Pluto"}),
    ]
    parking = {"Mercury": 240.0, "Venus": 250.0, "Sun": 260.0, "Mars": 270.0, "Pluto": 320.0}

    passed = []
    for level, active in stages:
        longitudes = dict(isolated)
        for name in ("Mercury", "Venus", "Sun", "Mars", "Pluto"):
            longitudes[name] = exact[name] if name in active else parking[name]
        bodies = synthetic_bodies(longitudes)
        print(f"W01 ALIGNMENT-SIZE LADDER {level} groups={group_names(bodies)} START", flush=True)
        result = layout(
            FinderMode.GREEK,
            bodies,
            target_solutions=5,
            budget={"max_node_candidates": 2000, "max_seconds": 60.0},
            context_label=f"W01-alignment-size-{level}",
        )
        assert_complete_valid_layout(result, bodies, FinderMode.GREEK)
        passed.append(level)
        print(f"W01 ALIGNMENT-SIZE LADDER {level} PASS", flush=True)
    print(f"W01 ALIGNMENT-SIZE LADDER COMPLETE passed={passed}", flush=True)


def test_w01_five_candidate_breakpoint_ladder(monkeypatch):
    """Find the first W01-shaped geometry that cannot produce five candidates quickly."""
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")
    passed = []
    for level, longitudes in W01_LADDER:
        bodies = synthetic_bodies(longitudes)
        print(f"W01 FIVE-CANDIDATE LADDER {level} START", flush=True)
        result = layout(
            FinderMode.GREEK,
            bodies,
            target_solutions=5,
            budget={"max_node_candidates": 2000, "max_seconds": 60.0},
            context_label=f"W01-five-candidate-ladder-{level}",
        )
        assert_complete_valid_layout(result, bodies, FinderMode.GREEK)
        passed.append(level)
        print(f"W01 FIVE-CANDIDATE LADDER {level} PASS", flush=True)
    print(f"W01 FIVE-CANDIDATE LADDER COMPLETE passed={passed}", flush=True)


def test_w01_five_candidate_deep_forensic(monkeypatch):
    """Single exact W01 run with full search attribution; diagnostic only."""
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "4")
    level, longitudes = W01_LADDER[-1]
    bodies = synthetic_bodies(longitudes)
    print(f"W01 FIVE-CANDIDATE DEEP FORENSIC {level} START", flush=True)
    started = time.monotonic()
    try:
        result = layout(
            FinderMode.GREEK,
            bodies,
            target_solutions=5,
            budget={"max_node_candidates": 2000, "max_seconds": 60.0},
            context_label="W01-five-candidate-deep-forensic",
        )
        assert_complete_valid_layout(result, bodies, FinderMode.GREEK)
    finally:
        print(
            f"W01 FIVE-CANDIDATE DEEP FORENSIC {level} END "
            f"elapsed={time.monotonic() - started:.3f}s",
            flush=True,
        )


def test_five_candidate_exact_w36_regression(monkeypatch):
    """Exact W36 Greek regression using the production five-candidate target."""
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")
    bodies = synthetic_bodies(W36_KNOWN_GOOD)
    print("FIVE-CANDIDATE REGRESSION W36 exact-W36 START", flush=True)
    result = layout(
        FinderMode.GREEK,
        bodies,
        target_solutions=5,
        budget={"max_node_candidates": 2000, "max_seconds": 120.0},
        context_label="five-candidate-regression-W36",
    )
    assert_complete_valid_layout(result, bodies, FinderMode.GREEK)
    print("FIVE-CANDIDATE REGRESSION W36 exact-W36 PASS", flush=True)
