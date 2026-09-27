#!/usr/bin/env python3
"""Stable launcher for the Planet Finder unit and system tests.

Run the small W02 conjunction regression first.  A promotion-cycle/lattice
failure there is structural, so there is no value spending many minutes on the
larger timeout-heavy suite before reporting it.
"""
from __future__ import annotations

import re
import subprocess
import sys

PREFLIGHT = [
    "tests/test_planet_finder_w02_conjunction.py",
]

FULL_TESTS = [
    "tests/test_planet_finder_candidate_generation.py",
    "tests/test_planet_finder_system.py",
    "tests/test_planet_finder_w02_conjunction.py",
]

SUMMARY_RE = re.compile(r"(?:\d+ failed|\d+ passed|\d+ error|\d+ skipped)")


def run_pytest(tests: list[str], *, maxfail: int | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "pytest", "-q"]
    if maxfail is not None:
        command.append(f"--maxfail={maxfail}")
    command.extend(tests)
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def print_failure_summary(output: str, *, heading: str = "PLANET FINDER TEST FAILURE SUMMARY") -> None:
    lines = output.splitlines()
    print(heading)

    conjunction_lines = [line for line in lines if "CONJUNCTION FAILURE" in line]
    for line in conjunction_lines:
        print(line.strip())

    failed_lines = [line for line in lines if line.startswith("FAILED ") or line.startswith("ERROR ")]
    for line in failed_lines:
        print(line)

    error_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("RuntimeError:", "AssertionError:", "TypeError:", "ValueError:")):
            if stripped not in error_lines:
                error_lines.append(stripped)
    for line in error_lines:
        print(line)

    summary = next((line for line in reversed(lines) if SUMMARY_RE.search(line)), None)
    if summary:
        print(summary)


def main() -> None:
    # Structural canary: stop after the first W02 conjunction failure.  This is
    # intentionally ahead of the full suite because promotion cycles and
    # canonical-lattice exhaustion make the later long searches non-actionable.
    preflight = run_pytest(PREFLIGHT, maxfail=1)
    if preflight.returncode != 0:
        print_failure_summary(
            preflight.stdout,
            heading="PLANET FINDER PRECHECK FAILURE — FULL SUITE SKIPPED",
        )
        raise SystemExit(preflight.returncode)

    result = run_pytest(FULL_TESTS)
    lines = result.stdout.splitlines()

    if result.returncode == 0:
        summary = next((line for line in reversed(lines) if SUMMARY_RE.search(line)), "Planet Finder tests passed.")
        print(summary)
        raise SystemExit(0)

    print_failure_summary(result.stdout)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
