#!/usr/bin/env python3
"""Generate a geocentric Planet Finder for one arbitrary UTC instant.

Uses the existing ephemeris and global label-placement solver unchanged.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from planet_finder_geometry import BODY_NAMES, BODY_SYMBOLS, CANONICAL
from planet_finder_rendering import render
from planet_finder_search import new_search_budget
from star_almanack_ephemeris import StarAlmanackEphemeris

MODES = {"greek": "greek", "latin": "latin", "mixed": "mixed"}


def parse_instant(value: str) -> datetime:
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("Provide an offset-aware ISO 8601 timestamp, e.g. 2026-10-26T21:00:00-07:00")
    return instant.astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instant", required=True, help="ISO 8601 date/time with UTC offset")
    parser.add_argument("--mode", choices=MODES, default="latin")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    instant = parse_instant(args.instant)
    engine = StarAlmanackEphemeris()
    bodies = [
        (BODY_SYMBOLS[BODY_NAMES[name]], name,
         engine.sample(BODY_NAMES[name], instant).longitude_deg)
        for name in CANONICAL
    ]
    # render() currently formats weekly headings. Replace only those two
    # presentation lines; the astronomical positions and layout are untouched.
    iso = instant.isocalendar()
    svg = render(iso.year, iso.week, instant.date(), args.mode, bodies,
                 budget=new_search_budget(), context_label=f"instant={instant.isoformat()}")
    from html import escape
    old_title = f"ISO {iso.year}-W{iso.week:02d} Planet Finder"
    svg = svg.replace(old_title, "Planet Finder — Selected Instant", 1)
    old_subtitle = f"Monday, {instant.strftime('%B')} {instant.day}, {iso.year} · 00:00 UTC"
    svg = svg.replace(old_subtitle, escape(instant.strftime("%Y-%m-%d %H:%M:%S UTC")), 1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(f"Generated {args.output} for {instant.isoformat()}")


if __name__ == "__main__":
    main()
