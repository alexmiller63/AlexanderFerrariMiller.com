#!/usr/bin/env python3
"""Provisional 2026–2035 solar eclipse catalog from the local eclipse engine.

No published eclipse dates or external ephemeris service is consulted.
A synodic-month grid proposes candidate dates; the engine searches geometry.
"""
import argparse
import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eclipse_engine import EclipseEngine

SEED = date(2026, 8, 12)  # lunation search anchor, not a reference prediction
SYNODIC_DAYS = 29.530588853
FIELDS = ["date_utc", "greatest_utc", "type", "axis_distance_km",
          "penumbra_margin_km", "central_margin_km", "core_radius_km",
          "status"]

def generate(start_year, end_year):
    engine = EclipseEngine()
    start, end = date(start_year, 1, 1), date(end_year + 1, 1, 1)
    results = {}
    # Expand the lunation grid past both ends to cover date rounding.
    for k in range(-180, 180):
        candidate = SEED + timedelta(days=round(k * SYNODIC_DAYS))
        if not start - timedelta(days=3) <= candidate < end + timedelta(days=3):
            continue
        event = engine.find_solar_eclipse(candidate.isoformat(), search_hours=48)
        if not event.eclipse_exists:
            continue
        event_day = date.fromisoformat(event.greatest_utc[:10])
        if not start <= event_day < end:
            continue
        g = event.geometry
        results[event.greatest_utc[:16]] = {
            "date_utc": event_day.isoformat(),
            "greatest_utc": event.greatest_utc,
            "type": event.eclipse_type,
            "axis_distance_km": round(g.axis_distance_km, 3),
            "penumbra_margin_km": round(g.eclipse_margin_km, 3),
            "central_margin_km": round(g.central_margin_km, 3),
            "core_radius_km": round(g.core_radius_km, 3),
            "status": "PROVISIONAL — geometry and times not independently validated",
        }
    return sorted(results.values(), key=lambda r: r["greatest_utc"])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2026)
    parser.add_argument("--end-year", type=int, default=2035)
    parser.add_argument("--output-dir", type=Path, default=Path("generated/eclipse-catalog"))
    args = parser.parse_args()
    if args.end_year < args.start_year:
        parser.error("end-year must not precede start-year")
    rows = generate(args.start_year, args.end_year)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / f"solar-eclipses-{args.start_year}-{args.end_year}.csv"
    json_path = args.output_dir / f"solar-eclipses-{args.start_year}-{args.end_year}.json"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps({"status": "provisional", "start_year": args.start_year,
        "end_year": args.end_year, "solar_eclipses": rows}, indent=2) + "\n")
    print(f"Wrote {len(rows)} provisional solar eclipses: {csv_path}, {json_path}")

if __name__ == "__main__":
    main()
