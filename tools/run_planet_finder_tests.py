#!/usr/bin/env python3
"""Stable launcher for the Planet Finder unit and system tests.

Run the small W02 conjunction regression first. A promotion-cycle/lattice
failure there is structural, so there is no value spending many minutes on the
larger timeout-heavy suite before reporting it.
"""
from __future__ import annotations

import os
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
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = "tools" if not existing else f"tools{os.pathsep}{existing}"
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )


def print_failure_summary(output: str, *, heading: str = "PLANET FINDER TEST FAILURE SUMMARY") -> None:
    lines = output.splitlines()
    print(heading)

    diagnostic_lines = [
        line for line in lines
        if "TERMINAL SEARCH DIAGNOSTIC" in line or "CAPPED SUMMARY" in line
    ]
    for line in diagnostic_lines:
        print(line.strip())

    conjunction_lines = [line for line in lines if "CONJUNCTION FAILURE" in line]
    for line in conjunction_lines:
        print(line.strip())

    failed_lines = [line for line in lines if line.startswith("FAILED ") or line.startswith("ERROR ")]
    for line in failed_lines:
        print(line)

    error_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith((
            "RuntimeError:", "AssertionError:", "TypeError:", "ValueError:",
            "ImportError:", "ModuleNotFoundError:", "SyntaxError:", "NameError:",
        )):
            if stripped not in error_lines:
                error_lines.append(stripped)
    for line in error_lines:
        print(line)

    summary = next((line for line in reversed(lines) if SUMMARY_RE.search(line)), None)
    if summary:
        print(summary)


def main() -> None:
    preflight = run_pytest(PREFLIGHT, maxfail=1)
    if preflight.returncode != 0:
        if preflight.returncode == 2:
            print("PLANET FINDER PRECHECK COLLECTION ERROR — FULL SUITE SKIPPED")
            print(preflight.stdout, end="" if preflight.stdout.endswith("\n") else "\n")
        else:
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
