#!/usr/bin/env python3
"""Compute Star Almanack best-visibility dates for a requested year."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
from pathlib import Path

REGRESSION_2026 = {
    "Aldebaran": "2026-01-12", "Rigel": "2026-01-21", "Capella": "2026-01-22",
    "Betelgeuse": "2026-01-31", "Sirius": "2026-02-13", "Procyon": "2026-02-27",
    "Pollux": "2026-02-28", "Regulus": "2026-04-08", "Spica": "2026-05-29",
    "Arcturus": "2026-06-11", "Antares": "2026-07-13", "Vega": "2026-08-15",
    "Albireo": "2026-08-29", "Altair": "2026-09-04", "Deneb": "2026-09-18",
}
REGRESSION_BAYER = {"Albireo": ("Bet1", "Cyg")}


def julian_date(x: dt.datetime) -> float:
    year, month = x.year, x.month
    day = x.day + (x.hour + (x.minute + x.second / 60.0) / 60.0) / 24.0
    if month <= 2:
        year -= 1; month += 12
    a = year // 100
    b = 2 - a + a // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5


def apparent_sun_ra_hours(x: dt.datetime) -> float:
    jd = julian_date(x); t = (jd - 2451545.0) / 36525.0
    mean_long = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360.0
    mean_anom = math.radians((357.52911 + t * (35999.05029 - 0.0001537 * t)) % 360.0)
    center = ((1.914602 - t * (0.004817 + 0.000014 * t)) * math.sin(mean_anom)
              + (0.019993 - 0.000101 * t) * math.sin(2 * mean_anom)
              + 0.000289 * math.sin(3 * mean_anom))
    true_long = mean_long + center
    omega = math.radians(125.04 - 1934.136 * t)
    apparent_long = math.radians((true_long - 0.00569 - 0.00478 * math.sin(omega)) % 360.0)
    seconds = 21.448 - t * (46.8150 + t * (0.00059 - t * 0.001813))
    mean_obliquity = 23.0 + (26.0 + seconds / 60.0) / 60.0
    obliquity = math.radians(mean_obliquity + 0.00256 * math.cos(omega))
    return math.degrees(math.atan2(math.cos(obliquity) * math.sin(apparent_long), math.cos(apparent_long))) % 360.0 / 15.0


def wrapped_hour_distance(a: float, b: float) -> float:
    return abs((a - b + 12.0) % 24.0 - 12.0)


def year_window(year: int) -> tuple[dt.datetime, dt.datetime]:
    return (dt.datetime(year, 1, 1) - dt.timedelta(hours=12),
            dt.datetime(year, 12, 31, 23, 59) + dt.timedelta(hours=12))


def best_visibility(ra_object_h: float, year: int) -> tuple[dt.datetime, dt.date]:
    target = (ra_object_h - 9.0) % 24.0
    start, end = year_window(year)
    best_distance = float("inf"); best_time = start
    x = start
    while x <= end:
        distance = wrapped_hour_distance(apparent_sun_ra_hours(x), target)
        if distance < best_distance: best_distance, best_time = distance, x
        x += dt.timedelta(hours=6)
    x = max(start, best_time - dt.timedelta(hours=8)); end_refine = min(end, best_time + dt.timedelta(hours=8))
    while x <= end_refine:
        distance = wrapped_hour_distance(apparent_sun_ra_hours(x), target)
        if distance < best_distance: best_distance, best_time = distance, x
        x += dt.timedelta(minutes=1)
    rounded_date = best_time.date()
    if rounded_date.year != year:
        raise RuntimeError(f"Best-visibility date escaped requested year {year}: {rounded_date}")
    return best_time, rounded_date


def iso_date(d: dt.date) -> str:
    iso = d.isocalendar(); return f"{iso.year}-W{iso.week:02d}-{iso.weekday}"


def magnitude_class(value: str) -> str:
    if not value: return ""
    return str(max(1, min(6, int(math.floor(float(value) + 0.5)))))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, nargs="?", default=Path("expanded-bayer-stars.csv"))
    parser.add_argument("output", type=Path, nargs="?", default=None)
    parser.add_argument("--year", type=int, default=2026)
    args = parser.parse_args()
    if args.output is None:
        args.output = Path(f"expanded-bayer-visibility-{args.year}.csv")

    with args.input.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows: raise SystemExit("Expanded Bayer catalog is empty")

    output = []; proper_to_date = {}; bayer_to_date = {}
    for row in rows:
        instant, date = best_visibility(float(row["ra_h"]), args.year)
        enriched = dict(row)
        enriched["best_instant_utc"] = instant.strftime("%Y-%m-%d %H:%M")
        enriched["best_date"] = date.isoformat(); enriched["iso"] = iso_date(date)
        enriched["mag_class"] = magnitude_class(row.get("mag", "")); output.append(enriched)
        if row.get("proper"): proper_to_date.setdefault(row["proper"], date.isoformat())
        bayer_to_date.setdefault((row["bayer_code"], row["con"]), date.isoformat())

    if args.year == 2026:
        failures = []
        for name, expected in REGRESSION_2026.items():
            actual = bayer_to_date.get(REGRESSION_BAYER[name]) if name in REGRESSION_BAYER else proper_to_date.get(name)
            if actual != expected: failures.append((name, expected, actual))
        if failures:
            for name, expected, actual in failures: print(f"FAIL {name}: expected {expected}, got {actual}")
            raise SystemExit(f"Best-visibility regression failed: {len(failures)}/15")
        print("Best-visibility regression: 15/15 PASS")

    fieldnames = list(rows[0].keys()) + ["best_instant_utc", "best_date", "iso", "mag_class"]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames); writer.writeheader(); writer.writerows(output)
    print(f"Year {args.year}: wrote {len(output)} dated α/β source rows to {args.output}")


if __name__ == "__main__": main()
