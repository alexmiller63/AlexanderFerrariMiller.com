"""Focused, fast W36 Planet Finder diagnostics.

Keep the expensive W01/W02/exact-W36 regression ladders out of the default
suite while we isolate the W36 preplacement/backtracking failure.
Production solver code is untouched.
"""

import pytest

from planet_finder_geometry import FinderMode, alignment_groups
from planet_finder_search import layout
from test_planet_finder_system import assert_complete_valid_layout, synthetic_bodies

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


def group_names(bodies):
    return sorted(tuple(item[1] for item in group) for group in alignment_groups(bodies))


def run_case(monkeypatch, label, longitudes, seconds):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")
    bodies = synthetic_bodies(longitudes)
    print(f"FAST DIAGNOSTIC {label}: groups={group_names(bodies)} budget={seconds}s", flush=True)
    try:
        result = layout(
            FinderMode.GREEK,
            bodies,
            target_solutions=1,
            budget={"max_node_candidates": 2000, "max_seconds": seconds},
            context_label=label,
        )
    except RuntimeError as exc:
        text = str(exc)
        expected = (
            "wall-clock budget exhausted" in text
            or "canonical candidate lattice exhausted" in text
            or "No collision-free Planet Finder layout found" in text
        )
        if not expected:
            raise
        print(f"FAST DIAGNOSTIC {label}: UNSOLVED {exc}", flush=True)
        return False
    assert_complete_valid_layout(result, bodies, FinderMode.GREEK)
    print(f"FAST DIAGNOSTIC {label}: PASS", flush=True)
    return True


def test_00_w36_control(monkeypatch):
    """Known nearby control must still solve quickly."""
    assert run_case(monkeypatch, "W36-control-Uranus-250", BASE_URANUS, 8.0)


def test_01_exact_w36_preplacement_probe(monkeypatch):
    """Exact W36 should reproduce the fixed-alignment -> Venus dead end quickly."""
    assert not run_case(monkeypatch, "W36-exact-preplacement-probe", W36_KNOWN_GOOD, 12.0)
