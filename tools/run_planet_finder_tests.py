#!/usr/bin/env python3
"""Temporary diagnostic launcher: run only the 1.7-degree Venus-Sun forensic case."""
from __future__ import annotations

import os
import subprocess
import sys

CONTROL = [
    "tests/test_planet_finder_w02_conjunction.py::test_greek_venus_sun_1_7_degree_forensic",
]


def main() -> None:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = "tools" if not existing else f"tools{os.pathsep}{existing}"
    command = [sys.executable, "-m", "pytest", "-q", "-s", *CONTROL]
    result = subprocess.run(command, env=env)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
