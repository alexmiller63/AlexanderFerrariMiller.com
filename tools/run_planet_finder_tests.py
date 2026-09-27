#!/usr/bin/env python3
"""Stable launcher for the Planet Finder unit and system tests."""
from __future__ import annotations

import re
import subprocess
import sys

TESTS = [
    "tests/test_planet_finder_candidate_generation.py",
    "tests/test_planet_finder_system.py",
    "tests/test_planet_finder_w02_conjunction.py",
]

SUMMARY_RE = re.compile(r"(?:\d+ failed|\d+ passed|\d+ error|\d+ skipped)")


def main() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *TESTS],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    lines = result.stdout.splitlines()

    if result.returncode == 0:
        summary = next((line for line in reversed(lines) if SUMMARY_RE.search(line)), "Planet Finder tests passed.")
        print(summary)
        raise SystemExit(0)

    print("PLANET FINDER TEST FAILURE SUMMARY")

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

    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
