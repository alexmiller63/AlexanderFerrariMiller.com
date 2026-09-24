#!/usr/bin/env python3
"""GitHub Actions launcher for the Planet Finder white-box stress test."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
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
