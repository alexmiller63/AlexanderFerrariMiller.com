#!/usr/bin/env python3
"""
Star Almanack eclipse coordinate bridge.

Purpose
-------
Put the high-precision ELP2000-82B lunar solution and the Almanack solar
solution into one common geocentric ecliptic-of-date coordinate frame so the
eclipse geometry in eclipse-math.md can consume ordinary Cartesian vectors.

This is a bridge layer, not a replacement ephemeris.

Inputs
------
- UTC civil date/time.
- Normalized ELP2000-82B coefficient JSON produced by normalize_elp82b.py.

Outputs
-------
- Geocentric Sun vector, kilometres.
- Geocentric Moon vector, kilometres.
- Ecliptic longitude/latitude and distance for each body.
- Sun-Moon angular separation.
- Wrapped longitude difference, useful for locating new/full moon.

Time
----
ELP2000-82B's reference routine is evaluated on a dynamical time argument.
For 2017-01-01 through the present build horizon, TAI-UTC = 37 s, so

    TT = UTC + 69.184 s.

TDB-TT is at the millisecond level and is intentionally left as a later
refinement. The validation layer reports this approximation explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import math

import lunar_elp
import ephemeris_engine


AU_KM = 149_597_870.7
TT_MINUS_UTC_SECONDS_2017_ONWARD = 69.184


@dataclass(frozen=True)
class EclipticVector:
    longitude_deg: float
    latitude_deg: float
    distance_km: float
    x_km: float
    y_km: float
    z_km: float


@dataclass(frozen=True)
class EclipseCoordinates:
    utc_iso: str
    jd_utc: float
    jd_tt_approx: float
    time_note: str
    sun: EclipticVector
    moon: EclipticVector
    separation_deg: float
    longitude_difference_deg: float


def julian_date_utc(dt: datetime) -> float:
    """Gregorian UTC datetime -> Julian Date."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)

    y = dt.year
    m = dt.month
    day_fraction = (
        dt.day
        + dt.hour / 24.0
        + dt.minute / 1440.0
        + (dt.second + dt.microsecond / 1_000_000.0) / 86400.0
    )

    if m <= 2:
        y -= 1
        m += 12

    a = y // 100
    b = 2 - a + a // 4

    return (
        math.floor(365.25 * (y + 4716))
        + math.floor(30.6001 * (m + 1))
        + day_fraction
        + b
        - 1524.5
    )


def utc_to_tt_approx(jd_utc: float) -> float:
    """UTC JD -> approximate TT JD for dates with TAI-UTC = 37 s."""
    return jd_utc + TT_MINUS_UTC_SECONDS_2017_ONWARD / 86400.0


def spherical_to_vector(longitude_deg: float, latitude_deg: float, distance_km: float) -> EclipticVector:
    lon = math.radians(longitude_deg)
    lat = math.radians(latitude_deg)
    clat = math.cos(lat)

    x = distance_km * clat * math.cos(lon)
    y = distance_km * clat * math.sin(lon)
    z = distance_km * math.sin(lat)

    return EclipticVector(
        longitude_deg=longitude_deg % 360.0,
        latitude_deg=latitude_deg,
        distance_km=distance_km,
        x_km=x,
        y_km=y,
        z_km=z,
    )


def angle_between(a: EclipticVector, b: EclipticVector) -> float:
    dot = a.x_km * b.x_km + a.y_km * b.y_km + a.z_km * b.z_km
    denom = a.distance_km * b.distance_km
    if denom == 0.0:
        raise ValueError("zero-length position vector")
    c = max(-1.0, min(1.0, dot / denom))
    return math.degrees(math.acos(c))


def wrap_signed_degrees(x: float) -> float:
    """Wrap an angle to [-180, 180)."""
    return (x + 180.0) % 360.0 - 180.0


def coordinates_at_utc(normalized: dict, dt: datetime, precision_rad: float = 0.0) -> EclipseCoordinates:
    jd_utc = julian_date_utc(dt)
    jd_tt = utc_to_tt_approx(jd_utc)

    # ELP evaluator returns the spherical solution before its final J2000
    # precession rotation. That spherical solution is the coordinate set we
    # pair with the Almanack's geocentric ecliptic-of-date solar longitude.
    moon_eval = lunar_elp.evaluate(normalized, jd_tt, precision_rad)
    ms = moon_eval.spherical

    moon = spherical_to_vector(
        math.degrees(ms.longitude_rad),
        math.degrees(ms.latitude_rad),
        ms.distance_km,
    )

    hour_utc = (
        dt.hour
        + dt.minute / 60.0
        + (dt.second + dt.microsecond / 1_000_000.0) / 3600.0
    )
    d = ephemeris_engine.day_number(dt.year, dt.month, dt.day, hour_utc)
    sp = ephemeris_engine.sun_position(d)

    sun = spherical_to_vector(
        sp.longitude_deg,
        0.0,
        sp.distance_au * AU_KM,
    )

    separation = angle_between(sun, moon)
    dlon = wrap_signed_degrees(moon.longitude_deg - sun.longitude_deg)

    return EclipseCoordinates(
        utc_iso=dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        jd_utc=jd_utc,
        jd_tt_approx=jd_tt,
        time_note=(
            "TT approximated as UTC + 69.184 s; TDB-TT millisecond correction "
            "not yet applied."
        ),
        sun=sun,
        moon=moon,
        separation_deg=separation,
        longitude_difference_deg=dlon,
    )


def as_dict(result: EclipseCoordinates) -> dict:
    def vec(v: EclipticVector) -> dict:
        return {
            "longitude_deg": v.longitude_deg,
            "latitude_deg": v.latitude_deg,
            "distance_km": v.distance_km,
            "x_km": v.x_km,
            "y_km": v.y_km,
            "z_km": v.z_km,
        }

    return {
        "utc": result.utc_iso,
        "jd_utc": result.jd_utc,
        "jd_tt_approx": result.jd_tt_approx,
        "time_note": result.time_note,
        "sun": vec(result.sun),
        "moon": vec(result.moon),
        "sun_moon_separation_deg": result.separation_deg,
        "moon_minus_sun_longitude_deg": result.longitude_difference_deg,
    }


def parse_utc(text: str) -> datetime:
    t = text.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Build common Sun/Moon eclipse vectors.")
    ap.add_argument("normalized_json", type=Path)
    ap.add_argument("utc", help="UTC instant, e.g. 2024-04-08T18:00:00Z")
    ap.add_argument(
        "--precision",
        type=float,
        default=0.0,
        help="ELP truncation level in radians; default 0 retains all terms",
    )
    ap.add_argument("--json", action="store_true", help="print JSON output")
    args = ap.parse_args(argv)

    normalized = json.loads(args.normalized_json.read_text(encoding="utf-8"))
    result = coordinates_at_utc(normalized, parse_utc(args.utc), args.precision)

    if args.json:
        print(json.dumps(as_dict(result), indent=2))
        return

    print(f"UTC: {result.utc_iso}")
    print(f"JD UTC: {result.jd_utc:.9f}")
    print(f"JD TT approx: {result.jd_tt_approx:.9f}")
    print(result.time_note)
    print()
    print("Sun, geocentric ecliptic-of-date:")
    print(f"  lon = {result.sun.longitude_deg:.9f} deg")
    print(f"  lat = {result.sun.latitude_deg:.9f} deg")
    print(f"  r   = {result.sun.distance_km:.3f} km")
    print(f"  xyz = ({result.sun.x_km:.3f}, {result.sun.y_km:.3f}, {result.sun.z_km:.3f}) km")
    print()
    print("Moon, geocentric ecliptic-of-date:")
    print(f"  lon = {result.moon.longitude_deg:.9f} deg")
    print(f"  lat = {result.moon.latitude_deg:.9f} deg")
    print(f"  r   = {result.moon.distance_km:.3f} km")
    print(f"  xyz = ({result.moon.x_km:.3f}, {result.moon.y_km:.3f}, {result.moon.z_km:.3f}) km")
    print()
    print(f"Sun-Moon separation: {result.separation_deg:.9f} deg")
    print(f"Moon - Sun longitude: {result.longitude_difference_deg:.9f} deg")


if __name__ == "__main__":
    main()
