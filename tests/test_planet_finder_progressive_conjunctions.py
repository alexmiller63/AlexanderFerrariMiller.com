"""Focused full-solver conjunction stress ladder: 4 through 8 bodies."""

from __future__ import annotations

import os
import time

import pytest

from planet_finder_geometry import CANONICAL, FinderMode, conjunction_groups
from planet_finder_search import layout
from planet_finder_validation import validate_layout


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


def _cluster(count: int, start: float = 100.0, step: float = 0.08):
    sky = _spread()
    members = list(CANONICAL[:count])
    for index, name in enumerate(members):
        sky[name] = (start + index * step) % 360.0
    return sky, members


def _bodies(longitudes):
    assert set(longitudes) == set(CANONICAL)
    return [(name.lower(), name, float(longitudes[name])) for name in CANONICAL]


def _append_summary(lines):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n\n")


CASES = []
for count in range(4, 9):
    sky, members = _cluster(count)
    CASES.append((count, sky, members))


@pytest.mark.parametrize(
    "count,longitudes,members",
    CASES,
    ids=[f"{count}-body-conjunction" for count, _, _ in CASES],
)
def test_conjunction_stress_4_through_8(count, longitudes, members, monkeypatch):
    """Run the real Greek Planet Finder solver and summarize each complexity level."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")

    bodies = _bodies(longitudes)
    groups = conjunction_groups(bodies)
    conjunction_name_groups = [[item[1] for item in group] for group in groups]
    conjoined = {name for group in conjunction_name_groups for name in group}

    input_lines = [
        f"### Conjunction stress — {count} bodies",
        "",
        f"- Intended members: {', '.join(members)}",
        f"- Classified groups: {conjunction_name_groups}",
        f"- Adjacent spacing: 0.08°",
        f"- Solver budget: 30.0 s, 10,000 candidates/body",
    ]
    _append_summary(input_lines)

    assert conjoined == set(members), (
        f"{count}-body classification mismatch: expected={members} got={conjunction_name_groups}"
    )

    started = time.monotonic()
    try:
        result = layout(
            FinderMode.GREEK,
            bodies,
            target_solutions=1,
            budget={"max_node_candidates": 10000, "max_seconds": 30.0},
            context_label=f"stress-{count}-body-conjunction",
        )
    except Exception as exc:
        elapsed = time.monotonic() - started
        _append_summary([
            f"#### Case result — {count} bodies",
            "",
            f"- Status: **FAIL**",
            f"- Elapsed: {elapsed:.3f} s",
            f"- Exception: `{type(exc).__name__}: {exc}`",
            "- Planner diagnostics for node/depth/rejection causes are recorded above.",
        ])
        raise

    elapsed = time.monotonic() - started
    actual = {name for _, name, _, _, _ in result}
    expected = {name for _, name, _ in bodies}
    valid, errors = validate_layout(FinderMode.GREEK, result)

    status = "PASS" if actual == expected and valid else "FAIL"
    _append_summary([
        f"#### Case result — {count} bodies",
        "",
        f"- Status: **{status}**",
        f"- Elapsed: {elapsed:.3f} s",
        f"- Placed: {len(actual)}/{len(expected)}",
        f"- Missing: {sorted(expected - actual)}",
        f"- Validation errors: {errors}",
        "- Planner diagnostics for node/depth/rejection causes are recorded above.",
    ])

    assert actual == expected, (
        f"{count}-body conjunction missing={sorted(expected - actual)} elapsed={elapsed:.3f}s"
    )
    assert valid, f"{count}-body conjunction validation errors={errors} elapsed={elapsed:.3f}s"

    print(
        f"CONJUNCTION STRESS PASS count={count} elapsed={elapsed:.3f}s "
        f"members={','.join(members)}",
        flush=True,
    )
