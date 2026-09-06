#!/usr/bin/env python3
"""
Star Almanack reconstructed Sun/Moon ephemeris engine.

Purpose
-------
Reproduce the Almanack's existing geocentric tropical ecliptic longitudes
without importing a published ephemeris table.

The model uses compact orbital elements plus the standard dominant lunar
perturbation terms. It is intended as the preserved computational machinery
under the Almanack, not as a claim to be a full modern numerical ephemeris.

Angles are degrees. Distances for the Moon are Earth radii.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import datetime, timezone


def rev(x: float) -> float:
    return x % 360.0


def sind(x: float) -> float:
    return math.sin(math.radians(x))


def cosd(x: float) -> float:
    return math.cos(math.radians(x))


def atan2d(y: float, x: float) -> float:
    return math.degrees(math.atan2(y, x))


def day_number(year: int, month: int, day: int, hour_utc: float = 0.0) -> float:
    """
    Days from 2000 Jan 0.0 UT for the compact orbital-element model.
    """
    return (
        367 * year
        - 7 * (year + (month + 9) // 12) // 4
        + 275 * month // 9
        + day
        - 730530
        + hour_utc / 24.0
    )


@dataclass
class SunPosition:
    longitude_deg: float
    distance_au: float
    mean_anomaly_deg: float
    longitude_perihelion_deg: float


@dataclass
class MoonPosition:
    longitude_deg: float
    latitude_deg: float
    distance_earth_radii: float


def sun_position(d: float) -> SunPosition:
    # Mean orbital elements
    w = 282.9404 + 4.70935e-5 * d
    e = 0.016709 - 1.151e-9 * d
    M = rev(356.0470 + 0.9856002585 * d)

    # First-order solution of Kepler's equation
    E = M + math.degrees(e * sind(M) * (1.0 + e * cosd(M)))

    x = cosd(E) - e
    y = math.sqrt(1.0 - e * e) * sind(E)
    r = math.hypot(x, y)
    v = atan2d(y, x)

    lon = rev(v + w)
    return SunPosition(lon, r, M, w)


def moon_position(d: float) -> MoonPosition:
    # Mean lunar orbital elements
    N = rev(125.1228 - 0.0529538083 * d)
    i = 5.1454
    w = rev(318.0634 + 0.1643573223 * d)
    a = 60.2666
    e = 0.054900
    M = rev(115.3654 + 13.0649929509 * d)

    # First-order solution of Kepler's equation
    E = M + math.degrees(e * sind(M) * (1.0 + e * cosd(M)))

    xv = a * (cosd(E) - e)
    yv = a * math.sqrt(1.0 - e * e) * sind(E)

    v = atan2d(yv, xv)
    r = math.hypot(xv, yv)

    # Ecliptic Cartesian coordinates
    xh = r * (cosd(N) * cosd(v + w) - sind(N) * sind(v + w) * cosd(i))
    yh = r * (sind(N) * cosd(v + w) + cosd(N) * sind(v + w) * cosd(i))
    zh = r * sind(v + w) * sind(i)

    lon = rev(atan2d(yh, xh))
    lat = atan2d(zh, math.hypot(xh, yh))

    # Dominant lunar perturbations
    sun = sun_position(d)
    Ls = rev(sun.mean_anomaly_deg + sun.longitude_perihelion_deg)
    Lm = rev(M + w + N)
    D = rev(Lm - Ls)
    F = rev(Lm - N)
    Ms = sun.mean_anomaly_deg

    lon += (
        -1.274 * sind(M - 2 * D)
        +0.658 * sind(2 * D)
        -0.186 * sind(Ms)
        -0.059 * sind(2 * M - 2 * D)
        -0.057 * sind(M - 2 * D + Ms)
        +0.053 * sind(M + 2 * D)
        +0.046 * sind(2 * D - Ms)
        +0.041 * sind(M - Ms)
        -0.035 * sind(D)
        -0.031 * sind(M + Ms)
        -0.015 * sind(2 * F - 2 * D)
        +0.011 * sind(M - 4 * D)
    )

    lat += (
        -0.173 * sind(F - 2 * D)
        -0.055 * sind(M - F - 2 * D)
        -0.046 * sind(M + F - 2 * D)
        +0.033 * sind(F + 2 * D)
        +0.017 * sind(2 * M + F)
    )

    return MoonPosition(rev(lon), lat, r)


def positions_at_utc(year: int, month: int, day: int, hour_utc: float = 0.0):
    d = day_number(year, month, day, hour_utc)
    return sun_position(d), moon_position(d)


if __name__ == "__main__":
    # Example: 2026-02-16 00:00 UTC
    s, m = positions_at_utc(2026, 2, 16)
    print(f"Sun  λ = {s.longitude_deg:.6f}°")
    print(f"Moon λ = {m.longitude_deg:.6f}°")
    print(f"Moon β = {m.latitude_deg:.6f}°")
