"""Week 5's crowded alignments must fit in every notation mode."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from planet_finder_geometry import CANONICAL, FinderMode
from planet_finder_search import layout
from planet_finder_validation import validate_layout


# Exact Monday snapshot recorded by the failed 2026-W05 workflow. No kernels
# or network are needed to exercise the same layout and routing problem.
W05_LONGITUDES = {
    "Sun": 306.03056569574136, "Moon": 33.437591624134086,
    "Mercury": 308.99734060500685, "Venus": 310.64497972243265,
    "Mars": 302.0381725217154, "Jupiter": 108.06329092807124,
    "Saturn": 358.0685665640884, "Ceres": 13.468911154887339,
    "Uranus": 57.49569099090363, "Neptune": 359.9815039889874,
    "Pluto": 303.50532713737965,
}


@pytest.mark.parametrize("mode", list(FinderMode))
def test_w05_five_candidate_contest_completes(monkeypatch, mode):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    bodies = [(name.lower(), name, W05_LONGITUDES[name]) for name in CANONICAL]
    result = layout(
        mode, bodies, target_solutions=5,
        budget={"max_node_candidates": 200, "max_seconds": 360.0},
        context_label="2026-W05-preplanning-regression",
    )
    assert len(result) == len(CANONICAL)
    assert {row[1] for row in result} == set(CANONICAL)
    valid, errors = validate_layout(mode, result)
    assert valid, errors
