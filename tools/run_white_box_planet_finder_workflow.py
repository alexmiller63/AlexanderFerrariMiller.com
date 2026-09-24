#!/usr/bin/env python3
"""GitHub Actions launcher for the Planet Finder white-box stress test.

Keep workflow YAML deliberately simple: dependency preparation and test
orchestration belong here in Python.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys


def ensure_dependencies() -> None:
    """Install runtime dependencies needed by production Planet Finder imports."""
    packages = []
    if importlib.util.find_spec("skyfield") is None:
        packages.append("skyfield")
    if packages:
        print("Installing white-box dependencies:", " ".join(packages), flush=True)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *packages],
            check=True,
        )


def main() -> None:
    ensure_dependencies()
    command = [
        sys.executable,
        "tools/white_box_planet_finder.py",
        "--mode", os.environ.get("WHITE_BOX_MODE", "greek"),
        "--center", os.environ.get("WHITE_BOX_CENTER", "15"),
        "--span", os.environ.get("WHITE_BOX_SPAN", "6"),
        "--candidates", os.environ.get("WHITE_BOX_CANDIDATES", "1"),
        "--body-cap", os.environ.get("WHITE_BOX_BODY_CAP", "200"),
        "--seconds", os.environ.get("WHITE_BOX_SECONDS", "180"),
        "--diagnostic", os.environ.get("WHITE_BOX_DIAGNOSTIC", "3"),
    ]
    print("White-box Planet Finder launcher:", " ".join(command), flush=True)
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
