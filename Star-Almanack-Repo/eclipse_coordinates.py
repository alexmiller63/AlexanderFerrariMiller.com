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
- UTC civil date/time at the presentation boundary.
- Normalized ELP2000-82B coefficient JSON produced by normalize_elp82b.py.

Outputs
-------
- Canonical JDTDB for the astronomical instant.
- Geocentric Sun vector, kilometres.
- Geocentric Moon vector, kilometres.
- Ecliptic longitude/latitude and distance for each body.
- Sun-Moon angular separation.
- Wrapped longitude difference, useful for locating new/full moon.

Time
----
Astronomical evaluation is performed on Julian Date TDB (JDTDB). UTC is used
only to accept/render the civil instant. Skyfield supplies the UTC -> TDB
conversion, including leap seconds and the periodic TDB-TT correction, so this
bridge no longer carries its former fixed UTC + 69.184 s TT approximation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import math

from skyfield.api import load

import lunar_elp
import ephemeris_engine


AU_KM = 149_597_870.7
J2000_DAY_ZERO_JD = 2451543.5  # 2000 Jan 0.0, basis of compact solar elements
_TIMESCALE = load.timescale(builtin=True)


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
    jd_tdb: float
    time_note: str
    sun: EclipticVector
    moon: EclipticVector
    separation_deg: float
    longitude_difference_deg: float


def julian_date_utc(dt: datetime) -> float:
    """Gregorian UTC datetime -> Julian Date UTC for reporting only."""
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


def utc_to_jd_tdb(dt: datetime) -> float:
    """Convert an aware civil UTC datetime to canonical JDTDB."""
    if dt.tzinfo is None:
        raise ValueError("UTC -> TDB conversion requires a timezone-aware datetime")
    utc = dt.astimezone(timezone.utc)
    return float(_TIMESCALE.from_datetime(utc).tdb)


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
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)

    jd_utc = julian_date_utc(dt)
    jd_tdb = utc_to_jd_tdb(dt)

    # ELP2000-82B is evaluated on the same canonical dynamical time coordinate
    # used by the rest of the Almanack event-solving architecture.
    moon_eval = lunar_elp.evaluate(normalized, jd_tdb, precision_rad)
    ms = moon_eval.spherical

    moon = spherical_to_vector(
        math.degrees(ms.longitude_rad),
        math.degrees(ms.latitude_rad),
        ms.distance_km,
    )

    # The compact solar coefficients use d = days since 2000 Jan 0.0. Evaluate
    # that independent variable on JDTDB as well, rather than mixing a UTC day
    # number with a dynamical-time lunar vector.
    d = jd_tdb - J2000_DAY_ZERO_JD
    sp = ephemeris_engine.sun_position(d)

    sun = spherical_to_vector(
        sp.longitude_deg,
        0.0,
        sp.distance_au * AU_KM,
    )

    separation = angle_between(sun, moon)
    dlon = wrap_signed_degrees(moon.longitude_deg - sun.longitude_deg)

    return EclipseCoordinates(
        utc_iso=dt.isoformat().replace("+00:00", "Z"),
        jd_utc=jd_utc,
        jd_tdb=jd_tdb,
        time_note=(
            "Astronomical evaluation uses JDTDB; UTC is retained only as the "
            "civil input/output representation."
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
        "jd_tdb": result.jd_tdb,
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
    print(f"JDTDB: {result.jd_tdb:.9f}")
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
