"""Diagnostic sweep for Venus-Sun separation from 2.0 down to 0.1 degrees."""

import time

import pytest

from planet_finder_geometry import CANONICAL, FinderMode, alignment_groups, conjunction_groups
from planet_finder_search import layout
from planet_finder_validation import validate_layout


def conjunction_case(separation):
    longitudes = {
        "Venus": 100.0,
        "Sun": 100.0 + separation,
        "Mercury": 20,
        "Mars": 150,
        "Pluto": 190,
        "Saturn": 230,
        "Neptune": 270,
        "Ceres": 310,
        "Moon": 350,
        "Uranus": 50,
        "Jupiter": 200,
    }
    assert set(longitudes) == set(CANONICAL)
    return [(name.lower(), name, float(longitudes[name])) for name in CANONICAL]


def _names(groups):
    return [[item[1] for item in group] for group in groups]


@pytest.mark.parametrize("tenths", range(20, 0, -1))
def test_greek_venus_sun_separation_sweep(monkeypatch, tenths):
    """Run each tenth-degree separation independently from 2.0 through 0.1."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "3")
    monkeypatch.setenv("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF", "1")

    separation = tenths / 10.0
    bodies = conjunction_case(separation)
    conjunctions = _names(conjunction_groups(bodies))
    alignments = _names(alignment_groups(bodies))

    print(
        "VENUS-SUN SWEEP INPUT: "
        f"separation={separation:.1f}deg "
        f"conjunction_groups={conjunctions} alignment_groups={alignments}",
        flush=True,
    )

    # Above 0.1 degrees the ordinary path must be used.  At exactly 0.1 the
    # conjunction-unit path is expected to become eligible.
    venus_sun_conjunction = any("Venus" in group and "Sun" in group for group in conjunctions)
    if separation > 0.1:
        assert not venus_sun_conjunction, (
            f"{separation:.1f}deg incorrectly classified as conjunction: {conjunctions}"
        )

    started = time.monotonic()
    result = layout(
        FinderMode.GREEK,
        bodies,
        target_solutions=1,
        budget={"max_node_candidates": 2000, "max_seconds": 60.0},
        context_label=f"venus-sun-{separation:.1f}deg-sweep",
    )
    elapsed = time.monotonic() - started

    expected = {name for _, name, _ in bodies}
    actual = [name for _, name, _, _, _ in result]
    missing = sorted(expected - set(actual))
    print(
        "VENUS-SUN SWEEP RESULT: "
        f"separation={separation:.1f}deg elapsed={elapsed:.3f}s "
        f"placed={len(actual)}/{len(expected)} missing={missing} order={actual}",
        flush=True,
    )

    assert len(actual) == len(expected), f"separation={separation:.1f}deg missing={missing}"
    assert set(actual) == expected
    valid, errors = validate_layout(FinderMode.GREEK, result)
    if not valid:
        print(
            f"VENUS-SUN SWEEP VALIDATION ERRORS separation={separation:.1f}deg: {errors}",
            flush=True,
        )
    assert valid, errors
