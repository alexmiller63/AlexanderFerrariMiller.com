#!/usr/bin/env python3
"""Provisional 2026–2035 solar and lunar eclipses from local geometry.

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
from eclipse_engine import EclipseEngine, gregorian_to_jd, jd_to_iso_utc
from lunar_eclipse_engine import find_lunar_eclipse

SEED = date(2026, 8, 12)  # lunation search anchor, not a reference prediction
SYNODIC_DAYS = 29.530588853
FIELDS = ["kind", "contacts_utc", "date_utc", "greatest_utc", "type", "axis_distance_km",
          "penumbra_margin_km", "central_margin_km", "core_radius_km",
          "status"]


def global_solar_boundaries(engine, greatest_jd, *, hours=12.0):
    """Approximate global first/last penumbral intersection with Earth.

    These are NOT observer-specific C1/C4 contacts. Search for sign changes
    in the existing eclipse-margin geometry and bisect each crossing.
    """
    def margin(jd):
        g = engine.geometry_at_utc_jd(jd)
        return g.eclipse_margin_km if g.q_min_km > 0 else float("inf")

    def crossing(left, right):
        fl = margin(left)
        for _ in range(55):
            mid = (left + right) / 2
            fm = margin(mid)
            if (fm <= 0) == (fl <= 0):
                left, fl = mid, fm
            else:
                right = mid
            if (right - left) * 86400 < 0.1:
                break
        return (left + right) / 2

    if margin(greatest_jd) > 0:
        raise ValueError("No penumbral intersection at greatest alignment")
    out = {}
    step = 10.0 / 1440.0
    for label, direction in (("global_begin", -1), ("global_end", 1)):
        inside = greatest_jd
        for n in range(1, int(hours * 6) + 1):
            outside = greatest_jd + direction * n * step
            if margin(outside) > 0:
                out[label] = jd_to_iso_utc(crossing(min(inside, outside), max(inside, outside)))
                break
            inside = outside
        else:
            raise RuntimeError(f"Unable to bracket {label} within {hours} hours")
    return out

def generate(start_year, end_year):
    engine = EclipseEngine()
    start, end = date(start_year, 1, 1), date(end_year + 1, 1, 1)
    results = {}
    print(f'Starting eclipse search {start_year}–{end_year}', flush=True)
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
        print(f'FOUND SOLAR {event.greatest_utc} {event.eclipse_type}', flush=True)
        results[event.greatest_utc[:16]] = {
            "kind": "solar", "contacts_utc": json.dumps(global_solar_boundaries(engine, event.greatest_jd_utc)),
            "date_utc": event_day.isoformat(),
            "greatest_utc": event.greatest_utc,
            "type": event.eclipse_type,
            "axis_distance_km": round(g.axis_distance_km, 3),
            "penumbra_margin_km": round(g.eclipse_margin_km, 3),
            "central_margin_km": round(g.central_margin_km, 3),
            "core_radius_km": round(g.core_radius_km, 3),
            "status": "PROVISIONAL — geometry and times not independently validated",
        }
    # Full moons lie approximately half a synodic month from each new moon.
    # Search each independent candidate against Earth's actual shadow.
    for k in range(-180, 180):
        candidate = SEED + timedelta(days=round((k + 0.5) * SYNODIC_DAYS))
        if not start - timedelta(days=3) <= candidate < end + timedelta(days=3):
            continue
        jd = gregorian_to_jd(candidate.year, candidate.month, candidate.day, 12.0)
        event = find_lunar_eclipse(engine, jd)
        if event is None:
            continue
        greatest = jd_to_iso_utc(event["greatest_jd_utc"])
        event_day = date.fromisoformat(greatest[:10])
        if not start <= event_day < end:
            continue
        g = event["geometry"]
        print(f"FOUND LUNAR {greatest} {event['type']} contacts={len(event['contacts_jd_utc'])}", flush=True)
        results["lunar:"+greatest[:16]] = {
            "kind": "lunar", "date_utc": event_day.isoformat(),
            "greatest_utc": greatest, "type": event["type"],
            "axis_distance_km": round(g.axis_distance_km, 3),
            "penumbra_margin_km": round(g.penumbral_margin_km, 3),
            "central_margin_km": round(g.umbral_margin_km, 3),
            "core_radius_km": round(g.umbra_radius_km, 3),
            "contacts_utc": json.dumps({key: jd_to_iso_utc(val)
                                         for key, val in sorted(event["contacts_jd_utc"].items())}),
            "status": "PROVISIONAL — geometry and times not independently validated",
        }
    print(f'Search complete: {len(results)} eclipses', flush=True)
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
    csv_path = args.output_dir / f"eclipses-{args.start_year}-{args.end_year}.csv"
    json_path = args.output_dir / f"eclipses-{args.start_year}-{args.end_year}.json"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps({"status": "provisional", "start_year": args.start_year,
        "end_year": args.end_year, "eclipses": rows}, indent=2) + "\n")
    print(f"Wrote {len(rows)} provisional solar and lunar eclipses: {csv_path}, {json_path}")

if __name__ == "__main__":
    main()
