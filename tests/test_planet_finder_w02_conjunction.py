"""Dynamically isolate the Venus-Sun conjunction breakpoint."""

import time

import pytest

from planet_finder_geometry import CANONICAL, FinderMode
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


def _try_separation(separation):
    bodies = conjunction_case(separation)
    started = time.monotonic()
    try:
        result = layout(
            FinderMode.GREEK,
            bodies,
            target_solutions=1,
            budget={"max_node_candidates": 2000, "max_seconds": 15.0},
            context_label=f"venus-sun-ladder-{separation:.3f}deg",
        )
        expected = {name for _, name, _ in bodies}
        actual = [name for _, name, _, _, _ in result]
        assert len(actual) == len(expected)
        assert set(actual) == expected
        valid, errors = validate_layout(FinderMode.GREEK, result)
        assert valid, errors
    except (RuntimeError, AssertionError) as exc:
        return False, time.monotonic() - started, str(exc)
    return True, time.monotonic() - started, ""


def test_greek_venus_sun_farthest_control(monkeypatch):
    """Walk from the known-good wide case down to the first failing separation."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "2")
    separations = [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0, 0.5]
    passed = []

    for separation in separations:
        ok, elapsed, detail = _try_separation(separation)
        status = "PASS" if ok else "FAIL"
        print(f"VENUS-SUN SEPARATION {separation:.3f} deg: {status} elapsed={elapsed:.3f}s")
        if not ok:
            print(f"VENUS-SUN FIRST FAILURE: {separation:.3f} deg after passes={passed}")
            if detail:
                print(f"VENUS-SUN FAILURE DETAIL: {detail}")
            pytest.fail(
                f"first Venus-Sun failure at {separation:.3f} deg; "
                f"wider passing separations={passed}"
            )
        passed.append(separation)

    print(f"VENUS-SUN LADDER COMPLETE: all separations passed {passed}")
