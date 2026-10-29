#!/usr/bin/env python3
"""Calculate geocentric planetary oppositions and greatest elongations, 2025–2028.

Uses the same cached DE440s kernel as Star Almanack. Does not claim to
calculate stations, occultations, close conjunctions or maximum brilliance.
"""
import argparse
import json
from pathlib import Path

from skyfield import almanac
from skyfield.searchlib import find_maxima
from star_almanack_ephemeris import StarAlmanackEphemeris

ROOT = Path(__file__).resolve().parents[1]
DOC = "https://rhodesmill.org/skyfield/almanac.html"
EXT = "https://rhodesmill.org/skyfield/searches.html"

def calculate(start_year=2025, end_year=2028):
    engine = StarAlmanackEphemeris()
    ts, eph = engine.ts, engine.planets
    earth, sun = engine.earth, engine.sun
    start, stop = ts.utc(start_year, 1, 1), ts.utc(end_year + 1, 1, 1)
    rows = []
    for name in ("Mars", "Jupiter", "Saturn", "Uranus", "Neptune"):
        target = engine.bodies[name.lower()]
        times, states = almanac.find_discrete(
            start, stop, almanac.oppositions_conjunctions(eph, target))
        for t, state in zip(times, states):
            if int(state) != 1:
                continue
            rows.append(dict(utc=t.utc_iso(), kind="opposition", planet=name,
                             description="Opposite the Sun in ecliptic longitude; generally visible through the night.",
                             source_url=DOC))
    for name in ("Mercury", "Venus"):
        target = engine.bodies[name.lower()]
        def separation(t):
            observer = earth.at(t)
            return observer.observe(sun).apparent().separation_from(
                observer.observe(target).apparent()).degrees
        separation.step_days = 4
        times, angles = find_maxima(start, stop, separation)
        for t, angle in zip(times, angles):
            if float(angle) < 10:
                continue
            rows.append(dict(utc=t.utc_iso(), kind="greatest elongation", planet=name,
                             description=f"Maximum angular separation from the Sun ({float(angle):.1f}°); look near twilight, with visibility depending on location and season.",
                             source_url=EXT))
    return sorted(rows, key=lambda row: (row["utc"], row["planet"]))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2025)
    parser.add_argument("--end-year", type=int, default=2028)
    parser.add_argument("--output", type=Path, default=ROOT / "data/planetary-events.json")
    args = parser.parse_args()
    if args.start_year > args.end_year:
        parser.error("start-year must be <= end-year")
    events = calculate(args.start_year, args.end_year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"events": events}, indent=2) + "\n", encoding="utf-8")
    print(f"Calculated {len(events)} planetary events to {args.output}")

if __name__ == "__main__":
    main()
