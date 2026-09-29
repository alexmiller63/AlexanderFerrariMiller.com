"""Focused forensic trace for the exact W01 Mercury failure.

Diagnostic only: this test changes no Planet Finder geometry or search policy.
It runs the exact W01 case at diagnostic level 3 so candidate rejection and
terminal-body detail are visible in the Actions log.
"""

from planet_finder_geometry import CANONICAL, FinderMode, alignment_groups, conjunction_groups
from planet_finder_search import layout
from planet_finder_validation import validate_layout


W01_EXACT = {
    "Sun": 277.511945972904,
    "Moon": 22.937571430229294,
    "Mercury": 264.1023447351197,
    "Venus": 275.4313050776394,
    "Mars": 280.39213202805865,
    "Jupiter": 111.74481470549088,
    "Saturn": 355.99936587038286,
    "Ceres": 6.453439627692317,
    "Uranus": 58.03460466327627,
    "Neptune": 359.4721293482971,
    "Pluto": 302.62909367404063,
}


def _bodies():
    return [(name.lower(), name, float(W01_EXACT[name])) for name in CANONICAL]


def _names(groups):
    return [[item[1] for item in group] for group in groups]


def test_exact_w01_mercury_rejection_trace(monkeypatch):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "3")
    bodies = _bodies()

    print(
        "W01 MERCURY FORENSIC INPUT: "
        f"Mercury={W01_EXACT['Mercury']:.12f}deg "
        f"conjunction_groups={_names(conjunction_groups(bodies))} "
        f"alignment_groups={_names(alignment_groups(bodies))}",
        flush=True,
    )

    result = layout(
        FinderMode.GREEK,
        bodies,
        target_solutions=1,
        budget={"max_node_candidates": 2000, "max_seconds": 60.0},
        context_label="W01-Mercury-forensic",
    )

    actual = [name for _, name, _, _, _ in result]
    missing = sorted(set(CANONICAL) - set(actual))
    print(
        "W01 MERCURY FORENSIC RESULT: "
        f"placed={len(actual)}/{len(CANONICAL)} missing={missing} order={actual}",
        flush=True,
    )

    assert len(actual) == len(CANONICAL), f"missing={missing}"
    assert set(actual) == set(CANONICAL)
    valid, errors = validate_layout(FinderMode.GREEK, result)
    assert valid, errors
