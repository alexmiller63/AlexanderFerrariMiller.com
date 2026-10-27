#!/usr/bin/env python3
"""Render a geocentric Planet Finder at an arbitrary UTC instant.

Requires the existing cached JPL source kernels and the unchanged layout solver.
Failure to place every label is fatal: never publish a partial chart.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from planet_finder_geometry import BODY_NAMES, BODY_SYMBOLS, CANONICAL, FinderMode
from planet_finder_rendering import render
from planet_finder_search import new_search_budget
from star_almanack_ephemeris import StarAlmanackEphemeris

MODES = {"greek": FinderMode.GREEK, "latin": FinderMode.ENGLISH, "mixed": FinderMode.MIXED}


def parse_instant(value: str) -> datetime:
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use ISO 8601, e.g. 1990-01-16T22:28:00Z") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise argparse.ArgumentTypeError("Specify an explicit UTC offset or Z")
    instant = instant.astimezone(timezone.utc)
    if not 1900 <= instant.year <= 2099:
        raise argparse.ArgumentTypeError("Supported dates: 1900–2099")
    return instant


def generate(instant: datetime, mode: str, engine: StarAlmanackEphemeris) -> str:
    bodies = []
    for name in CANONICAL:
        key = BODY_NAMES[name]
        sample = engine.sample(key, instant)
        bodies.append((BODY_SYMBOLS[key], name, sample.longitude_deg))
    iso = instant.isocalendar()
    return render(
        iso.year, iso.week, instant.date(), MODES[mode], bodies,
        budget=new_search_budget(),
        context_label=f"instant={instant.isoformat()} mode={mode}",
        instant_utc=instant.strftime("%Y-%m-%d %H:%M UTC"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instant", type=parse_instant, required=True, help="ISO 8601 with Z or UTC offset")
    parser.add_argument("--mode", choices=MODES, default="greek")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Do not create or truncate the destination until both calculations and
    # collision-free placement have completed successfully.
    svg = generate(args.instant, args.mode, StarAlmanackEphemeris())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_name(args.output.name + ".tmp")
    try:
        temp.write_text(svg, encoding="utf-8")
        temp.replace(args.output)
    finally:
        temp.unlink(missing_ok=True)
    print(f"Planet Finder generated: {args.output}")


if __name__ == "__main__":
    main()
