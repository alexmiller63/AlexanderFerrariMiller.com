"""Focused diagnostic for the Venus-Sun 1.7 degree ordinary-placement case."""

import time

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


def test_greek_venus_sun_1_7_degree_forensic(monkeypatch):
    """Trace the 1.7 degree case through the ordinary Planet Finder path."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "3")
    monkeypatch.setenv("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF", "1")

    separation = 1.70
    bodies = conjunction_case(separation)
    conjunctions = _names(conjunction_groups(bodies))
    alignments = _names(alignment_groups(bodies))

    print(
        "VENUS-SUN 1.700 FORENSIC INPUT: "
        f"Venus=100.000000deg Sun=101.700000deg separation={separation:.3f}deg "
        f"conjunction_groups={conjunctions} alignment_groups={alignments}",
        flush=True,
    )

    # 1.7 degrees must not enter conjunction-specific handling.  Make that
    # assumption explicit in the diagnostic so a threshold regression is
    # immediately visible instead of being mistaken for a geometry failure.
    assert not any("Venus" in group and "Sun" in group for group in conjunctions), (
        f"1.700deg incorrectly classified as conjunction: {conjunctions}"
    )

    started = time.monotonic()
    result = layout(
        FinderMode.GREEK,
        bodies,
        target_solutions=1,
        budget={"max_node_candidates": 2000, "max_seconds": 60.0},
        context_label="venus-sun-1.700deg-forensic",
    )
    elapsed = time.monotonic() - started

    expected = {name for _, name, _ in bodies}
    actual = [name for _, name, _, _, _ in result]
    missing = sorted(expected - set(actual))
    print(
        "VENUS-SUN 1.700 FORENSIC RESULT: "
        f"elapsed={elapsed:.3f}s placed={len(actual)}/{len(expected)} "
        f"missing={missing} order={actual}",
        flush=True,
    )

    assert len(actual) == len(expected), f"missing={missing}"
    assert set(actual) == expected
    valid, errors = validate_layout(FinderMode.GREEK, result)
    if not valid:
        print(f"VENUS-SUN 1.700 VALIDATION ERRORS: {errors}", flush=True)
    assert valid, errors
