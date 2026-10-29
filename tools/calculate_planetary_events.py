#!/usr/bin/env python3
"""Calculate geocentric planetary phenomena for Winter 2024–Winter 2027.

Uses the same cached DE440s kernel as Star Almanack, including retrograde and
direct stations in apparent ecliptic longitude. Does not calculate occultations,
close conjunctions or maximum brilliance.
"""
import argparse
import json
from pathlib import Path

from skyfield import almanac
from skyfield.framelib import ecliptic_frame
from skyfield.searchlib import find_maxima
from star_almanack_ephemeris import StarAlmanackEphemeris

ROOT = Path(__file__).resolve().parents[1]
DOC = "https://rhodesmill.org/skyfield/almanac.html"
EXT = "https://rhodesmill.org/skyfield/searches.html"
COORD = "https://rhodesmill.org/skyfield/coordinates.html#ecliptic-coordinates"
STATION_PLANETS = ("Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune")


def station_events(engine, start, stop):
    """Find reversals in apparent geocentric ecliptic longitude of date.

    A centered two-minute displacement includes light-time and apparent-position
    corrections. Wrap differences through +/-180 degrees so crossing longitude
    zero cannot create a spurious station. The two-day search step is shorter
    than even Mercury's shortest retrograde interval. Refine to 0.1 second;
    published instants are rounded to seconds, not a claim of that accuracy.
    """
    rows = []
    half_step = 1.0 / 1440.0
    for name in STATION_PLANETS:
        target = engine.bodies[name.lower()]

        def retrograde(t):
            before = engine.earth.at(t - half_step).observe(target).apparent()
            after = engine.earth.at(t + half_step).observe(target).apparent()
            lon_before = before.frame_latlon(ecliptic_frame)[1].degrees
            lon_after = after.frame_latlon(ecliptic_frame)[1].degrees
            return (lon_after - lon_before + 180.0) % 360.0 - 180.0 < 0.0

        retrograde.step_days = 2.0
        times, states = almanac.find_discrete(start, stop, retrograde, epsilon=0.1 / 86400.0)
        for t, state in zip(times, states):
            kind = "retrograde station" if state else "direct station"
            direction = "westward (retrograde)" if state else "eastward (direct)"
            rows.append(dict(
                utc=t.utc_iso(), kind=kind, planet=name,
                description=f"Apparent motion in geocentric ecliptic longitude turns {direction} against the background stars.",
                source_url=COORD,
            ))
    return rows

def calculate(start_year=2024, end_year=2028):
    engine = StarAlmanackEphemeris()
    ts, eph = engine.ts, engine.planets
    earth, sun = engine.earth, engine.sun
    # Match the seasonal calendar's civil-day bounds, including Winter 2027
    # into March 2028. Avoid emitting events for unscaffolded December/April
    # weeks outside the requested seasons.
    seasons = almanac.seasons(eph)
    starts, _ = almanac.find_discrete(
        ts.utc(start_year, 12, 1), ts.utc(start_year + 1, 1, 1), seasons)
    stops, _ = almanac.find_discrete(
        ts.utc(end_year, 3, 1), ts.utc(end_year, 4, 1), seasons)
    first, last = starts[0].utc_datetime().date(), stops[0].utc_datetime().date()
    start, stop = ts.utc(first.year, first.month, first.day), ts.utc(last.year, last.month, last.day)
    rows = station_events(engine, start, stop)
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
    parser.add_argument("--start-year", type=int, default=2024)
    parser.add_argument("--end-year", type=int, default=2028)
    parser.add_argument("--output", type=Path, default=ROOT / "data/planetary-events.json")
    args = parser.parse_args()
    if args.start_year >= args.end_year:
        parser.error("start-year must precede end-year (winter start through spring end)")
    events = calculate(args.start_year, args.end_year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"events": events}, indent=2) + "\n", encoding="utf-8")
    print(f"Calculated {len(events)} planetary events to {args.output}")

if __name__ == "__main__":
    main()
