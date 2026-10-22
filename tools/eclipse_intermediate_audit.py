#!/usr/bin/env python3
"""Read-only intermediate-value audit of the existing solar eclipse engine.

All vectors are geocentric, mean ecliptic J2000, in kilometers.
Reference instants are used ONLY for same-time comparison, not as orbital inputs.
"""
import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from eclipse_engine import EclipseEngine, gregorian_to_jd, tai_minus_utc_seconds

def jd_from_iso(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    return gregorian_to_jd(dt.year, dt.month, dt.day, dt.hour + dt.minute/60 + (dt.second + dt.microsecond/1e6)/3600)

def row(engine, case, label, jd):
    g = engine.geometry_at_utc_jd(jd)
    moon, sun = g.moon, g.sun
    dot = moon.dot(sun) / (moon.norm() * sun.norm())
    separation = math.degrees(math.acos(max(-1., min(1., dot)))) * 3600
    return dict(case=case, sample=label, jd_utc=f"{jd:.12f}",
                jd_tdb_approx=f"{g.jd_tdb_approx:.12f}",
                tt_minus_utc_s=f"{(g.jd_tdb_approx-jd)*86400:.6f}",
                tai_minus_utc_s=tai_minus_utc_seconds(jd),
                moon_x_km=moon.x, moon_y_km=moon.y, moon_z_km=moon.z,
                sun_x_km=sun.x, sun_y_km=sun.y, sun_z_km=sun.z,
                moon_range_km=moon.norm(), sun_range_km=sun.norm(),
                separation_arcsec=separation,
                sun_moon_distance_km=g.sun_moon_distance_km,
                q_min_km=g.q_min_km, axis_distance_km=g.axis_distance_km,
                core_radius_km=g.core_radius_km,
                penumbra_radius_km=g.penumbra_radius_km,
                eclipse_margin_km=g.eclipse_margin_km,
                central_margin_km=g.central_margin_km,
                eclipse_type=g.eclipse_type)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dates", nargs="+", default=["2026-08-12","2027-02-06","2027-08-02","2028-01-26","2028-07-22"])
    p.add_argument("--references", type=Path, help="Optional JSON mapping date to reference UTC ISO timestamp")
    p.add_argument("--out", type=Path, default=Path("eclipse-intermediate-audit.csv"))
    args=p.parse_args()
    refs=json.loads(args.references.read_text()) if args.references else {}
    engine=EclipseEngine()
    rows=[]
    for date in args.dates:
        event=engine.find_solar_eclipse(date)
        center=event.greatest_jd_utc
        for offset in (-120,-60,0,60,120):
            rows.append(row(engine,date,f"predicted_{offset:+d}s",center+offset/86400))
        if date in refs:
            ref_jd=jd_from_iso(refs[date])
            rows.append(row(engine,date,"reference_same_instant",ref_jd))
            rows.append(row(engine,date,"predicted_at_reference_minus_60s",ref_jd-60/86400))
            rows.append(row(engine,date,"predicted_at_reference_plus_60s",ref_jd+60/86400))
            print(f"{date}: predicted minus reference = {(center-ref_jd)*86400:+.3f} seconds")
        else:
            print(f"{date}: no reference timestamp supplied; no same-instant reference comparison")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} samples to {args.out}")

if __name__=="__main__":
    main()
