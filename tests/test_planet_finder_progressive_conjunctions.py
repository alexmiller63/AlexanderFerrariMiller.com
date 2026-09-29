"""Progressive full-solver QA: simple sky through all bodies in one conjunction."""

import time

import pytest

from planet_finder_geometry import CANONICAL, FinderMode, conjunction_groups
from planet_finder_search import layout
from planet_finder_validation import validate_layout


def _bodies(longitudes):
    assert set(longitudes) == set(CANONICAL)
    return [(name.lower(), name, float(longitudes[name])) for name in CANONICAL]


def _spread():
    return {
        "Sun": 0.0,
        "Mercury": 32.0,
        "Venus": 64.0,
        "Moon": 96.0,
        "Mars": 128.0,
        "Ceres": 160.0,
        "Jupiter": 192.0,
        "Saturn": 224.0,
        "Uranus": 256.0,
        "Neptune": 288.0,
        "Pluto": 320.0,
    }


def _cluster(names, start=100.0, step=0.08):
    sky = _spread()
    for index, name in enumerate(names):
        sky[name] = (start + index * step) % 360.0
    return sky


CASES = [
    ("00-wide-baseline", _spread(), 0),
    ("01-one-alignment-pair", {**_spread(), "Sun": 100.0, "Venus": 102.0}, 0),
    ("02-two-alignment-pairs", {**_spread(), "Sun": 100.0, "Venus": 102.0, "Mars": 200.0, "Jupiter": 202.0}, 0),
    ("03-former-1deg-cliff", {**_spread(), "Sun": 100.0, "Venus": 101.0}, 0),
    ("04-near-conjunction-0.2deg", {**_spread(), "Sun": 100.0, "Venus": 100.2}, 0),
    ("05-one-true-conjunction", {**_spread(), "Sun": 100.0, "Venus": 100.08}, 2),
    ("06-two-independent-conjunctions", {**_spread(), "Sun": 100.0, "Venus": 100.08, "Mars": 220.0, "Jupiter": 220.08}, 4),
    ("07-three-body-conjunction", _cluster(["Sun", "Mercury", "Venus"]), 3),
    ("08-five-body-conjunction", _cluster(["Sun", "Mercury", "Venus", "Moon", "Mars"]), 5),
    ("09-eight-body-conjunction", _cluster(["Sun", "Mercury", "Venus", "Moon", "Mars", "Ceres", "Jupiter", "Saturn"]), 8),
    ("10-all-bodies-one-conjunction", _cluster(list(CANONICAL)), len(CANONICAL)),
]


@pytest.mark.parametrize("label,longitudes,expected_conjoined", CASES, ids=[case[0] for case in CASES])
def test_progressive_full_solver_conjunction_ladder(label, longitudes, expected_conjoined, monkeypatch):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")
    bodies = _bodies(longitudes)
    groups = conjunction_groups(bodies)
    conjoined = {item[1] for group in groups for item in group}
    assert len(conjoined) == expected_conjoined, (
        f"{label}: expected {expected_conjoined} bodies participating in conjunctions, "
        f"got {sorted(conjoined)}"
    )

    started = time.monotonic()
    result = layout(
        FinderMode.GREEK,
        bodies,
        target_solutions=1,
        budget={"max_node_candidates": 10000, "max_seconds": 30.0},
        context_label=f"progressive-{label}",
    )
    elapsed = time.monotonic() - started
    actual = {name for _, name, _, _, _ in result}
    expected = {name for _, name, _ in bodies}

    assert actual == expected, f"{label}: missing={sorted(expected - actual)} elapsed={elapsed:.3f}s"
    valid, errors = validate_layout(FinderMode.GREEK, result)
    assert valid, f"{label}: validation errors={errors} elapsed={elapsed:.3f}s"

    print(
        f"PROGRESSIVE CONJUNCTION PASS level={label} conjoined={expected_conjoined}/{len(CANONICAL)} "
        f"elapsed={elapsed:.3f}s",
        flush=True,
    )
