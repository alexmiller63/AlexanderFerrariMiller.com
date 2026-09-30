"""W36 regression gate plus stop-on-first-failure W1/W2 Planet Finder ladders.

W36 is the known-good production baseline and must remain green before the
progressive W01/W02 stress ladders matter. Exact W01/W02 remain immutable
endpoints.
"""

from datetime import date

import pytest

from populate_ephemeris import computed_ephemeris
from star_almanack_ephemeris import StarAlmanackEphemeris
from planet_finder_geometry import BODY_NAMES, BODY_SYMBOLS, CANONICAL, FinderMode
from planet_finder_search import layout
from test_planet_finder_system import (
    W01_LADDER,
    W02_LADDER,
    assert_alignment_labels_follow_lambda,
    assert_complete_valid_layout,
    synthetic_bodies,
)

MODES = [FinderMode.GREEK, FinderMode.LATIN, FinderMode.MIXED]
REGRESSION_SECONDS = 60.0


def production_week_bodies(year, week):
    """Build the exact body set used by the production weekly generator."""
    date.fromisocalendar(year, week, 1)  # validate the ISO week
    needed = {BODY_NAMES[name] for name in CANONICAL}
    generated = computed_ephemeris(year, StarAlmanackEphemeris())
    values = {key: generated[key][week - 1][0] for key in needed}
    return [
        (BODY_SYMBOLS[BODY_NAMES[name]], name, values[BODY_NAMES[name]] % 360)
        for name in CANONICAL
    ]


@pytest.mark.parametrize("mode", MODES)
def test_w36_known_good_regression_gate(monkeypatch, mode):
    """Never improve W01/W02 by sacrificing the hard-won W36 baseline."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")
    bodies = production_week_bodies(2026, 36)
    print(f"REGRESSION GATE W36 {mode.value}: START", flush=True)
    try:
        result = layout(
            mode,
            bodies,
            target_solutions=1,
            budget={"max_node_candidates": 2000, "max_seconds": REGRESSION_SECONDS},
            context_label=f"regression-W36-{mode.value}",
        )
        assert_complete_valid_layout(result, bodies, mode)
    except Exception as exc:
        print(
            f"REGRESSION GATE SUMMARY: week=W36 mode={mode.value} "
            f"FAIL error={type(exc).__name__}: {exc}",
            flush=True,
        )
        raise
    print(f"REGRESSION GATE SUMMARY: week=W36 mode={mode.value} PASS", flush=True)


def run_ladder(monkeypatch, week, mode, ladder):
    passed = []
    for level, longitudes in ladder:
        exact = level.startswith("exact-")
        monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "2" if exact else "0")
        bodies = synthetic_bodies(longitudes)
        print(f"LADDER {week} {mode.value}: {level} START", flush=True)
        try:
            result = layout(
                mode,
                bodies,
                target_solutions=1,
                budget={"max_node_candidates": 2000, "max_seconds": REGRESSION_SECONDS},
                context_label=f"ultimate-{week}-{level}-{mode.value}",
            )
            assert_complete_valid_layout(result, bodies, mode)
            if (
                mode != FinderMode.GREEK
                and level in {"both-real-alignments", "exact-W01", "all-W02-groups", "exact-W02"}
            ):
                assert_alignment_labels_follow_lambda(result, bodies)
        except Exception as exc:
            print(
                f"LADDER SUMMARY: week={week} mode={mode.value} "
                f"passed={passed} FIRST_FAILURE={level} error={type(exc).__name__}: {exc}",
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
def test_ultimate_w01_ladder(monkeypatch, mode):
    run_ladder(monkeypatch, "W01", mode, W01_LADDER)


@pytest.mark.parametrize("mode", MODES)
def test_ultimate_w02_ladder(monkeypatch, mode):
    run_ladder(monkeypatch, "W02", mode, W02_LADDER)
