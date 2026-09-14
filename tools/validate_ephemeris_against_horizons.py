#!/usr/bin/env python3
"""Validate Star Almanack weekly ephemerides against JPL Horizons.

This is a validation-only tool. Horizons values are never written into Almanack
production data. The local Star Almanack engine remains the production source.

Acceptance criterion for publication positions:
- apparent geocentric ecliptic longitude error <= 1 arcminute
- apparent geocentric ecliptic latitude error <= 1 arcminute

The comparison uses the same weekly Monday 00:00 UTC epochs published by the
Almanack and Horizons quantity 31 (observer ecliptic longitude/latitude).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import urllib.parse
import urllib.request
from datetime import date, timedelta

from star_almanack_ephemeris import StarAlmanackEphemeris

HORIZONS_API = "https://ssd.jpl.nasa.gov/api/horizons.api"
TARGETS = [
    ("sun", "10"),
    ("moon", "301"),
    ("mercury", "199"),
    ("venus", "299"),
    ("mars", "499"),
    ("jupiter", "599"),
    ("saturn", "699"),
    ("uranus", "799"),
    ("neptune", "899"),
    ("pluto", "999"),
    ("ceres", "1;"),
]


def week_count(year: int) -> int:
    return date(year, 12, 28).isocalendar().week


def angular_error_deg(a: float, b: float) -> float:
    """Smallest absolute circular difference in degrees."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def fetch_horizons_weekly(year: int, command: str) -> list[tuple[float, float]]:
    count = week_count(year)
    first = date.fromisocalendar(year, 1, 1)
    last = date.fromisocalendar(year, count, 1)
    params = {
        "format": "json",
        "COMMAND": f"'{command}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",
        "START_TIME": f"'{first.isoformat()} 00:00'",
        "STOP_TIME": f"'{(last + timedelta(days=1)).isoformat()} 00:00'",
        "STEP_SIZE": "'7 d'",
        "QUANTITIES": "'31'",
        "CSV_FORMAT": "'YES'",
        "ANG_FORMAT": "'DEG'",
        "CAL_FORMAT": "'CAL'",
        "TIME_DIGITS": "'SECONDS'",
    }
    request = urllib.request.Request(
        HORIZONS_API + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "Star-Almanack-validation/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
    text = payload.get("result", "")
    lines = text.splitlines()
    try:
        header_line = next(line for line in lines if "ObsEcLon" in line and "ObsEcLat" in line)
        start = lines.index("$$SOE") + 1
        stop = lines.index("$$EOE")
    except (StopIteration, ValueError) as exc:
        raise RuntimeError(f"Unexpected Horizons response for COMMAND={command}:\n{text[:2000]}") from exc

    header = [cell.strip() for cell in next(csv.reader([header_line]))]
    lon_index = header.index("ObsEcLon")
    lat_index = header.index("ObsEcLat")
    values: list[tuple[float, float]] = []
    for line in lines[start:stop]:
        if not line.strip():
            continue
        row = next(csv.reader([line]))
        values.append((float(row[lon_index].strip()), float(row[lat_index].strip())))
    if len(values) != count:
        raise RuntimeError(
            f"Horizons returned {len(values)} weekly rows for {command}; expected {count}"
        )
    return values


def validate_year(year: int, tolerance_arcmin: float) -> int:
    engine = StarAlmanackEphemeris()
    count = week_count(year)
    failures = 0
    print(f"Validation year: {year}")
    print(f"Locked tolerance: {tolerance_arcmin:.3f} arcmin for longitude and latitude")
    print("Reference: JPL Horizons quantity 31, validation only")

    for key, command in TARGETS:
        reference = fetch_horizons_weekly(year, command)
        max_lon = (-1.0, None)
        max_lat = (-1.0, None)
        body_failures = 0

        for week in range(1, count + 1):
            monday = date.fromisocalendar(year, week, 1)
            local = engine.sample(key, monday)
            ref_lon, ref_lat = reference[week - 1]
            lon_error = angular_error_deg(local.longitude_deg, ref_lon) * 60.0
            lat_error = abs(local.latitude_deg - ref_lat) * 60.0

            if lon_error > max_lon[0]:
                max_lon = (lon_error, monday)
            if lat_error > max_lat[0]:
                max_lat = (lat_error, monday)
            if lon_error > tolerance_arcmin or lat_error > tolerance_arcmin:
                body_failures += 1
                failures += 1
                print(
                    f"FAIL {key:8s} {monday.isoformat()} "
                    f"dLon={lon_error:.4f}' dLat={lat_error:.4f}' "
                    f"local=({local.longitude_deg:.8f},{local.latitude_deg:.8f}) "
                    f"Horizons=({ref_lon:.8f},{ref_lat:.8f})"
                )

        status = "PASS" if body_failures == 0 else "FAIL"
        print(
            f"{status} {key:8s} weeks={count} "
            f"max_dLon={max_lon[0]:.4f}'@{max_lon[1]} "
            f"max_dLat={max_lat[0]:.4f}'@{max_lat[1]} "
            f"failures={body_failures}"
        )

    if failures:
        print(f"OVERALL FAIL: {failures} weekly body samples exceeded tolerance")
        return 1
    print("OVERALL PASS: every weekly longitude and latitude sample is within tolerance")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("year", nargs="?", type=int, default=2026)
    parser.add_argument("--tolerance-arcmin", type=float, default=1.0)
    args = parser.parse_args()
    if args.tolerance_arcmin <= 0:
        parser.error("--tolerance-arcmin must be positive")
    return validate_year(args.year, args.tolerance_arcmin)


if __name__ == "__main__":
    raise SystemExit(main())
