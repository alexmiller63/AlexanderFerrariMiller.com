#!/usr/bin/env python3
"""Planet Finder targeted test launcher."""
from __future__ import annotations

import os
import subprocess
import sys

CONTROL = [
    "tests/test_planet_finder_ultimate_ladders.py::test_w01_five_candidate_breakpoint_ladder",
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
