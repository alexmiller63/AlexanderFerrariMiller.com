#!/usr/bin/env python3
"""Generate canonical weekly Planet Finder SVGs.

The implementation is split into focused modules while this file remains the
public entry point and compatibility facade.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from populate_ephemeris import computed_ephemeris, week_count
from star_almanack_ephemeris import StarAlmanackEphemeris
from almanack_paths import week_dir

from planet_finder_geometry import *
from planet_finder_search import (
    DEFAULT_CANDIDATE_LAYOUTS,
    DEFAULT_MAX_NODE_CANDIDATES,
    DEFAULT_MAX_SEARCH_SECONDS,
    layout,
    new_search_budget,
    validate_layout,
)
from planet_finder_render import render

ROOT = Path(__file__).resolve().parents[1]

def generate_week(year: int, week: int):
    if not 1 <= week <= week_count(year):
        raise ValueError(f"Invalid ISO week {year}-W{week:02d}")
    monday = date.fromisocalendar(year, week, 1)
    needed = {BODY_NAMES[name] for name in CANONICAL}
    engine = StarAlmanackEphemeris()
    generated = computed_ephemeris(year, engine)
    values = {key: generated[key][week - 1][0] for key in needed}
    bodies = [(BODY_SYMBOLS[BODY_NAMES[name]], name, values[BODY_NAMES[name]] % 360) for name in CANONICAL]
    outdir = week_dir(year, week) / "finders"
    outdir.mkdir(parents=True, exist_ok=True)
    filenames = {
        FinderMode.GREEK: "planet-finder-greek-symbols.svg",
        FinderMode.LATIN: "planet-finder-latin.svg",
        FinderMode.MIXED: "planet-finder-mixed-learner.svg",
    }
    # Generate the complete 3-mode set in memory first. A failure in any mode
    # must leave the week's published finder set untouched; never publish a
    # partial Greek/Latin/Mixed result.
    rendered = {}
    for mode, filename in filenames.items():
        rendered[filename] = render(year, week, monday, mode, bodies)

    # render()/layout() independently validates every selected layout before it
    # returns. Only after all 3 modes succeed do we replace the week's files.
    for filename, svg in rendered.items():
        (outdir / filename).write_text(svg, encoding="utf-8")
    print(f"Generated collision-free Planet Finders for ISO {year}-W{week:02d} from internal calculations")


def parse_args():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--current", action="store_true", help="generate the current UTC ISO week")
    g.add_argument("--year", type=int, help="ISO week-year")
    p.add_argument("--week", type=int, help="ISO week number; required with --year")
    args = p.parse_args()
    if args.year is not None and args.week is None:
        p.error("--week is required with --year")
    return args


def main():
    args = parse_args()
    if args.current:
        today = date.today()
        iso = today.isocalendar()
        year, week = iso.year, iso.week
    else:
        year, week = args.year, args.week
    generate_week(year, week)


if __name__ == "__main__":
    main()