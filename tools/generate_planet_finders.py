#!/usr/bin/env python3
"""Generate canonical weekly Planet Finder SVGs from Star Almanack calculations.

The renderer follows the frozen Planet Finder specification. It consumes the
same internally calculated planetary positions as the weekly ephemeris and does
not query Horizons or another answer service.
"""
from __future__ import annotations

import argparse
import html
import math
import os
import time
from dataclasses import dataclass
from datetime import date
from enum import Enum, auto
from pathlib import Path

from populate_ephemeris import TARGETS, computed_ephemeris, week_count
from star_almanack_ephemeris import StarAlmanackEphemeris
from almanack_paths import week_dir
from planet_finder_search import DepthNodeBudgetExhausted, SearchOutcome, new_search_budget, layout, diagnostic_print
from planet_finder_validation import validate_layout
from planet_finder_rendering import polyline, render
from planet_finder_geometry import (
    W, H, CX, CY, RO, RI,
    LABEL_RIM_CLEARANCE, LABEL_COLLISION_PADDING,
    IMMUTABLE_LEADER_CLEARANCE, PLACED_LABEL_LEADER_CLEARANCE,
    LEADER_TO_LEADER_CLEARANCE, LEADER_RIM_CLEARANCE,
    LABEL_LENGTH, PREFERRED_LABEL_RADII, EXPANDED_LABEL_RADII, ROUTE_RADII,
    SIGNS, BODY_SYMBOLS, BODY_NAMES, CANONICAL,
    DEFAULT_CANDIDATE_LAYOUTS, DEFAULT_MAX_NODE_CANDIDATES,
    DEFAULT_MAX_SEARCH_SECONDS,
    FinderMode, Body, Box,
    xy, boxes_overlap, segment_hits_box, point_segment_distance,
    segments_too_close, leaders_too_close, leader_hits_zodiac_rim, minimum_leader_separation,
    label_size, reserved_boxes, candidate_positions,
    legal_candidate_positions, route,
)

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
    diagnostic_print(f"Generated collision-free Planet Finders for ISO {year}-W{week:02d} from internal calculations")


def parse_args():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--current", action="store_true", help="generate the current UTC ISO week")
    g.add_argument("--year", type=int, help="ISO week-year")
    p.add_argument("--week", type=int, help="ISO week number; required with --year")
    p.add_argument("--diagnostic-level", type=int, default=None, metavar="N", help="diagnostic verbosity: 0=silent, 1=major events, 2=search detail, 3=forensic detail")
    args = p.parse_args()
    if args.year is not None and args.week is None:
        p.error("--week is required with --year")
    return args


def main():
    args = parse_args()
    if args.diagnostic_level is not None:
        if args.diagnostic_level < 0:
            raise SystemExit("--diagnostic-level must be zero or greater")
        os.environ["PLANET_FINDER_DIAGNOSTIC_LEVEL"] = str(args.diagnostic_level)
    if args.current:
        today = date.today()
        iso = today.isocalendar()
        year, week = iso.year, iso.week
    else:
        year, week = args.year, args.week
    generate_week(year, week)


if __name__ == "__main__":
    main()