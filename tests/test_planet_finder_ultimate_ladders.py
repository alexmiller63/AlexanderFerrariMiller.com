"""Stop-on-first-failure W1/W2 ultimate Planet Finder ladders.

Each week/mode is one true progressive test: advance only while the previous
rung passes.  Exact W01/W02 remain the immutable endpoints.
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
REGRESSION_SECONDS = 60.0


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
