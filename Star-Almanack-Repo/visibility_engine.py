#!/usr/bin/env python3
"""Year-parameterized Star Almanack observer-first visibility engine."""
from __future__ import annotations

import datetime as dt
import math


def julian_date(x: dt.datetime) -> float:
    year, month = x.year, x.month
    day = x.day + (x.hour + (x.minute + x.second / 60.0) / 60.0) / 24.0
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5


def apparent_sun_ra_hours(x: dt.datetime) -> float:
    jd = julian_date(x)
    t = (jd - 2451545.0) / 36525.0
    mean_long = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360.0
    mean_anom = math.radians((357.52911 + t * (35999.05029 - 0.0001537 * t)) % 360.0)
    center = ((1.914602 - t * (0.004817 + 0.000014 * t)) * math.sin(mean_anom)
              + (0.019993 - 0.000101 * t) * math.sin(2.0 * mean_anom)
              + 0.000289 * math.sin(3.0 * mean_anom))
    true_long = mean_long + center
    omega = math.radians(125.04 - 1934.136 * t)
    apparent_long = math.radians((true_long - 0.00569 - 0.00478 * math.sin(omega)) % 360.0)
    seconds = 21.448 - t * (46.8150 + t * (0.00059 - t * 0.001813))
    mean_obliquity = 23.0 + (26.0 + seconds / 60.0) / 60.0
    obliquity = math.radians(mean_obliquity + 0.00256 * math.cos(omega))
    ra_deg = math.degrees(math.atan2(math.cos(obliquity) * math.sin(apparent_long), math.cos(apparent_long))) % 360.0
    return ra_deg / 15.0


def wrapped_hour_distance(a: float, b: float) -> float:
    return abs((a - b + 12.0) % 24.0 - 12.0)


def year_window(year: int) -> tuple[dt.datetime, dt.datetime]:
    """Return the annual observing cycle used by the Almanack.

    Start at noon on the preceding Dec 31 so a true optimum can round into
    Jan 1 of the requested year. End at the requested Dec 31 so an optimum
    can round into Jan 1 of the following year. This mirrors the established
    2026 calculation rather than silently changing its date convention.
    """
    return (dt.datetime(year, 1, 1) - dt.timedelta(hours=12),
            dt.datetime(year, 12, 31, 23, 59))


def best_visibility(ra_object_h: float, year: int) -> tuple[dt.datetime, dt.date]:
    target = (ra_object_h - 9.0) % 24.0
    start, end = year_window(year)
    best_distance = float("inf")
    best_time = start
    x = start
    while x <= end:
        distance = wrapped_hour_distance(apparent_sun_ra_hours(x), target)
        if distance < best_distance:
            best_distance, best_time = distance, x
        x += dt.timedelta(hours=6)
    start_refine = max(start, best_time - dt.timedelta(hours=8))
    end_refine = min(end, best_time + dt.timedelta(hours=8))
    x = start_refine
    while x <= end_refine:
        distance = wrapped_hour_distance(apparent_sun_ra_hours(x), target)
        if distance < best_distance:
            best_distance, best_time = distance, x
        x += dt.timedelta(minutes=1)
    rounded_date = (best_time + dt.timedelta(hours=12)).date()
    if not dt.date(year, 1, 1) <= rounded_date <= dt.date(year + 1, 1, 1):
        raise RuntimeError(f"Best-visibility date escaped requested observing cycle {year}: {rounded_date}")
    return best_time, rounded_date


def iso_date(d: dt.date) -> str:
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}-{iso.weekday}"