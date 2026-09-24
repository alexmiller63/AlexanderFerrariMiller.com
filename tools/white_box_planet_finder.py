#!/usr/bin/env python3
"""Deterministic white-box stress harness for Planet Finder search.

This deliberately puts every Solar-System body inside one zodiac sign so the
layout engine can be studied under severe crowding without astronomical input.
It calls the production search code; only the body longitudes are synthetic.
"""

from __future__ import annotations

import argparse
import os
import time

from planet_finder_geometry import BODY_SYMBOLS, CANONICAL, FinderMode
from planet_finder_search import layout, new_search_budget


def crowded_bodies(center: float = 15.0, span: float = 6.0):
    """Return all canonical bodies packed deterministically around one longitude."""
    if not 0.0 <= center < 360.0:
        raise ValueError("center must be in [0, 360)")
    if not 0.0 <= span < 30.0:
        raise ValueError("span must be in [0, 30) so all bodies remain in one sign")

    count = len(CANONICAL)
    if count == 1:
        longitudes = [center]
    else:
        start = center - span / 2.0
        step = span / (count - 1)
        longitudes = [start + i * step for i in range(count)]

    bodies = []
    for name, longitude in zip(CANONICAL, longitudes):
        key = name.lower()
        symbol = BODY_SYMBOLS[key]
        bodies.append((symbol, name, longitude % 360.0))
    return bodies


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=[m.value for m in FinderMode], default="greek")
    parser.add_argument("--center", type=float, default=15.0,
                        help="center longitude; 15 degrees is the middle of Aries")
    parser.add_argument("--span", type=float, default=6.0,
                        help="total longitude span occupied by all bodies")
    parser.add_argument("--candidates", type=int, default=1)
    parser.add_argument("--body-cap", type=int, default=200)
    parser.add_argument("--seconds", type=float, default=180.0)
    parser.add_argument("--diagnostic", type=int, default=3)
    args = parser.parse_args()

    os.environ["PLANET_FINDER_DIAGNOSTIC_LEVEL"] = str(args.diagnostic)
    os.environ["PLANET_FINDER_MAX_NODE_CANDIDATES"] = str(args.body_cap)
    os.environ["PLANET_FINDER_MAX_SECONDS"] = str(args.seconds)

    bodies = crowded_bodies(args.center, args.span)
    print("WHITE BOX: all bodies deliberately crowded into one zodiac sign")
    print(f"mode={args.mode} center={args.center:g} span={args.span:g} candidates={args.candidates}")
    print("synthetic longitudes:")
    for symbol, name, longitude in bodies:
        print(f"  {name:8s} {symbol}  {longitude:8.3f}°")

    budget = new_search_budget()
    started = time.monotonic()
    try:
        result = layout(
            FinderMode(args.mode),
            bodies,
            target_solutions=args.candidates,
            budget=budget,
            context_label="WHITE-BOX-CROWDED",
        )
    except Exception as exc:
        elapsed = time.monotonic() - started
        print(f"WHITE BOX RESULT: FAILURE after {elapsed:.3f}s: {type(exc).__name__}: {exc}")
        raise

    elapsed = time.monotonic() - started
    print(f"WHITE BOX RESULT: SUCCESS after {elapsed:.3f}s; placements={len(result)}")


if __name__ == "__main__":
    main()
