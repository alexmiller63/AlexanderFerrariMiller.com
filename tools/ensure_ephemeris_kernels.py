#!/usr/bin/env python3
"""Ensure locally cached JPL/NAIF source kernels are present."""
from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlretrieve

from skyfield.api import Loader

DEFAULT_CACHE_DIR = Path(".cache/skyfield")
DE440S_FILENAME = "de440s.bsp"
CERES_FILENAME = "ceres_1900_2100.bsp"
CERES_URL = (
    "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/asteroids/"
    "a_old_versions/ceres_1900_2100.bsp"
)


def ensure_de440s(root: Path) -> None:
    path = root / DE440S_FILENAME
    if path.exists():
        print(f"Reusing cached {path} ({path.stat().st_size:,} bytes)")
        return
    print("Downloading JPL/NAIF DE440s source kernel for local calculation")
    Loader(str(root)).download(DE440S_FILENAME)


def ensure_ceres(root: Path) -> None:
    path = root / CERES_FILENAME
    if path.exists():
        print(f"Reusing cached {path} ({path.stat().st_size:,} bytes)")
        return
    print("Downloading JPL/NAIF Ceres source kernel under NAIF distribution rules")
    urlretrieve(CERES_URL, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--ceres", action="store_true", help="also ensure the Ceres source kernel")
    args = parser.parse_args()

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    ensure_de440s(args.cache_dir)
    if args.ceres:
        ensure_ceres(args.cache_dir)


if __name__ == "__main__":
    main()
