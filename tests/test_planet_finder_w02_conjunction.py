"""Diagnostic sweep for Venus-Sun separation from 2.0 down to 0.1 degrees."""

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


def test_greek_venus_sun_separation_sweep(monkeypatch):
    """Walk downward by tenths and stop immediately at the first failure."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "3")
    monkeypatch.setenv("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF", "1")

    expected_names = {name for _, name, _ in conjunction_case(2.0)}

    for tenths in range(20, 0, -1):
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
            budget={"max_node_candidates": 2000, "max_seconds": 15.0},
            context_label=f"venus-sun-{separation:.1f}deg-sweep",
        )
        elapsed = time.monotonic() - started

        actual = [name for _, name, _, _, _ in result]
        missing = sorted(expected_names - set(actual))
        print(
            "VENUS-SUN SWEEP RESULT: "
            f"separation={separation:.1f}deg elapsed={elapsed:.3f}s "
            f"placed={len(actual)}/{len(expected_names)} missing={missing} order={actual}",
            flush=True,
        )

        assert len(actual) == len(expected_names), (
            f"FIRST FAILURE separation={separation:.1f}deg elapsed={elapsed:.3f}s missing={missing}"
        )
        assert set(actual) == expected_names
        valid, errors = validate_layout(FinderMode.GREEK, result)
        if not valid:
            print(
                f"VENUS-SUN SWEEP VALIDATION ERRORS separation={separation:.1f}deg: {errors}",
                flush=True,
            )
        assert valid, f"FIRST FAILURE separation={separation:.1f}deg errors={errors}"

    print("VENUS-SUN SWEEP COMPLETE: all separations 2.0deg through 0.1deg passed", flush=True)
