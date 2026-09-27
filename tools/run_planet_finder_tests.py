#!/usr/bin/env python3
"""Stable launcher for the Planet Finder unit and system tests."""
from __future__ import annotations

import subprocess
import sys

TESTS = [
    "tests/test_planet_finder_candidate_generation.py",
    "tests/test_planet_finder_system.py",
    "tests/test_planet_finder_w02_conjunction.py",
]


def main() -> None:
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q", *TESTS]))


if __name__ == "__main__":
    main()
