#!/usr/bin/env python3
"""Provisional 2026–2035 solar and lunar eclipses from local geometry.

No published eclipse dates or external ephemeris service is consulted.
A synodic-month grid proposes candidate dates; the engine searches geometry.
"""
import argparse
import csv
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eclipse_engine import EclipseEngine, gregorian_to_jd, jd_to_iso_utc, EARTH_RADIUS_KM, SUN_RADIUS_KM, MOON_RADIUS_KM
from lunar_eclipse_engine import find_lunar_eclipse, SHADOW_EARTH_RADIUS_FACTOR

SEED = date(2026, 8, 12)  # lunation search anchor, not a reference prediction
SYNODIC_DAYS = 29.530588853
FIELDS = ["id", "detail_path", "kind", "position_source", "classification_basis", "surface_core_radius_min_km", "surface_core_radius_max_km", "shadow_earth_radius_factor", "contacts_utc", "date_utc", "greatest_utc", "type", "axis_distance_km",
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

def solar_surface_classification(engine, greatest_jd):
    """Classify the entire central event using its near-side Earth surface.

    A positive signed core radius denotes umbra (total); a negative one
    denotes antumbra (annular). Opposite signs along the central path mean
    hybrid. This is a spherical-Earth model, not a detailed path solution.
    """
    greatest = engine.geometry_at_utc_jd(greatest_jd)
    if greatest.axis_distance_km >= EARTH_RADIUS_KM:
        return {"type": greatest.eclipse_type, "contacts": {},
                "classification_basis": "No central-axis crossing of spherical Earth"}

    def boundary(direction):
        inside = greatest_jd
        for i in range(1, 73):
            outside = greatest_jd + direction * i * (10.0 / 1440.0)
            if engine.geometry_at_utc_jd(outside).axis_distance_km >= EARTH_RADIUS_KM:
                for _ in range(50):
                    mid = (inside + outside) / 2.0
                    if engine.geometry_at_utc_jd(mid).axis_distance_km < EARTH_RADIUS_KM:
                        inside = mid
                    else:
                        outside = mid
                    if abs(inside - outside) * 86400.0 < 0.01:
                        break
                return (inside + outside) / 2.0
        raise RuntimeError("Could not bracket central shadow-axis crossing")

    begin, end = boundary(-1), boundary(1)
    values = []
    for jd in [begin + (end - begin) * i / 120 for i in range(121)] + [greatest_jd]:
        g = engine.geometry_at_utc_jd(jd)
        near_surface_distance = math.sqrt(max(0.0, EARTH_RADIUS_KM**2 - g.axis_distance_km**2))
        cone_slope = (SUN_RADIUS_KM - MOON_RADIUS_KM) / g.sun_moon_distance_km
        values.append(g.core_radius_km + near_surface_distance * cone_slope)
    low, high = min(values), max(values)
    kind = "hybrid" if low < 0 < high else "total" if high > 0 else "annular"
    return {"type": kind,
            "classification_basis": "Near-side surface along the central-axis path; spherical Earth",
            "surface_core_radius_min_km": round(low, 3),
            "surface_core_radius_max_km": round(high, 3),
            "contacts": {"axis_entry": jd_to_iso_utc(begin), "axis_exit": jd_to_iso_utc(end)}}


def generate(start_year, end_year, kernel=None):
    if kernel is not None:
        from kernel_eclipse_engine import KernelEclipseEngine
        engine = KernelEclipseEngine(kernel)
        position_source = "JPL DE440s kernel; Star Almanack shadow geometry"
    else:
        engine = EclipseEngine()
        position_source = "ELP2000-82B Moon and compact solar model; Star Almanack shadow geometry"
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
        solar_contacts = global_solar_boundaries(engine, event.greatest_jd_utc)
        surface = solar_surface_classification(engine, event.greatest_jd_utc)
        solar_contacts.update(surface["contacts"])
        print(
            f"FOUND SOLAR {event.greatest_utc} {surface['type']} "
            f"global_begin={solar_contacts['global_begin']} "
            f"global_end={solar_contacts['global_end']}",
            flush=True,
        )
        results[event.greatest_utc[:16]] = {
            "kind": "solar", "contacts_utc": json.dumps(solar_contacts),
            "position_source": position_source,
            "date_utc": event_day.isoformat(),
            "greatest_utc": event.greatest_utc,
            "type": surface["type"],
            **{key: value for key, value in surface.items() if key not in ("type", "contacts")},
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
        event = find_lunar_eclipse(engine, jd, search_hours=48.0)
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
            "position_source": position_source,
            "shadow_earth_radius_factor": SHADOW_EARTH_RADIUS_FACTOR,
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
    parser.add_argument("--start-year", type=int, default=2025)
    parser.add_argument("--end-year", type=int, default=2036)
    parser.add_argument("--output-dir", type=Path, default=Path("generated/eclipse-catalog"))
    parser.add_argument("--kernel", type=Path, help="Local DE440s kernel for Sun and Moon positions")
    args = parser.parse_args()
    if args.end_year < args.start_year:
        parser.error("end-year must not precede start-year")
    rows = generate(args.start_year, args.end_year, kernel=args.kernel)
    # Registry identity is persistent across recalculations. Never derive a new
    # identifier solely because an improved ephemeris shifts the UTC date.
    registry_path = args.output_dir / "eclipse-registry.json"
    previous = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {"events": []}
    old_events = previous.get("events", [])
    assigned = set()
    for row in rows:
        day = date.fromisoformat(row["date_utc"])
        matches = [item for item in old_events
                   if item["kind"] == row["kind"]
                   and abs((date.fromisoformat(item["date_utc"]) - day).days) <= 3
                   and item["id"] not in assigned]
        if len(matches) > 1:
            raise RuntimeError(f"Ambiguous permanent eclipse identity: {row['date_utc']}")
        event_id = matches[0]["id"] if matches else f"ECL-{day:%Y-%m-%d}-{'S' if row['kind'] == 'solar' else 'L'}"
        if event_id in assigned:
            raise RuntimeError(f"Duplicate eclipse identity: {event_id}")
        assigned.add(event_id)
        row["id"] = event_id
        row["detail_path"] = f"eclipses/{event_id}.html"
    # Preserve entries outside the requested build window.
    retained = [item for item in old_events
                if not args.start_year <= date.fromisoformat(item["date_utc"]).year <= args.end_year]
    registry_events = retained + [dict(id=r["id"], kind=r["kind"], date_utc=r["date_utc"],
                                      detail_path=r["detail_path"]) for r in rows]
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps({"schema_version": 1, "events": sorted(registry_events,
        key=lambda item: (item["date_utc"], item["kind"]))}, indent=2) + "\n", encoding="utf-8")
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

