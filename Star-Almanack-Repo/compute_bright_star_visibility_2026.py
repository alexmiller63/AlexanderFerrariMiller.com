#!/usr/bin/env python3
"""Compute 2026 best-visibility dates for the reconciled bright-star layer.

Uses the same observer-first rule and solar-RA implementation as the audited
alpha/beta Bayer visibility computation. The output includes all reconciled
bright-star systems; `new_non_alpha_beta=yes` identifies the systems that add
new stellar content to the expanded Almanack.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
from pathlib import Path

from compute_bayer_visibility_2026 import (
    REGRESSION,
    REGRESSION_BAYER,
    apparent_sun_ra_hours,
    best_visibility,
    iso_date,
    wrapped_hour_distance,
)


def magnitude_class(value: str) -> str:
    """Whole-number Almanack display class; decimal V remains in source fields."""
    if not value:
        return ""
    mag = float(value)
    return str(max(1, min(6, int(math.floor(mag + 0.5)))))


def normalize_to_iso_2026(ra_object_h: float, instant: dt.datetime, date: dt.date) -> tuple[dt.datetime, dt.date]:
    """Move an adjacent-year annual occurrence to the occurrence inside ISO 2026.

    The base solver intentionally searches across the Gregorian boundary. For
    objects whose first equally valid annual solution lands in late December
    2025, refine the next annual occurrence rather than rejecting the object.
    This is the same ISO-week-year principle used for W53 dates in January 2027.
    """
    if date.isocalendar().year == 2026:
        return instant, date

    direction = 1 if date.isocalendar().year < 2026 else -1
    target = (ra_object_h - 9.0) % 24.0
    center = instant + dt.timedelta(days=direction * 365)

    best_time = center
    best_distance = wrapped_hour_distance(apparent_sun_ra_hours(center), target)
    x = center - dt.timedelta(days=3)
    end = center + dt.timedelta(days=3)
    while x <= end:
        distance = wrapped_hour_distance(apparent_sun_ra_hours(x), target)
        if distance < best_distance:
            best_distance = distance
            best_time = x
        x += dt.timedelta(minutes=5)

    # Final one-minute refinement around the best five-minute sample.
    x = best_time - dt.timedelta(minutes=10)
    end = best_time + dt.timedelta(minutes=10)
    while x <= end:
        distance = wrapped_hour_distance(apparent_sun_ra_hours(x), target)
        if distance < best_distance:
            best_distance = distance
            best_time = x
        x += dt.timedelta(minutes=1)

    rounded_date = (best_time + dt.timedelta(hours=12)).date()
    return best_time, rounded_date


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, nargs="?", default=Path("bright-stars-2mag.csv"))
    parser.add_argument("output", type=Path, nargs="?", default=Path("bright-star-visibility-2026.csv"))
    args = parser.parse_args()

    with args.input.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit("Bright-star catalog is empty")

    output = []
    proper_to_date: dict[str, str] = {}
    bayer_to_date: dict[tuple[str, str], str] = {}

    for row in rows:
        ra = float(row["ra_h"])
        instant, date = best_visibility(ra)
        instant, date = normalize_to_iso_2026(ra, instant, date)
        enriched = dict(row)
        enriched["best_instant_utc"] = instant.strftime("%Y-%m-%d %H:%M")
        enriched["best_date"] = date.isoformat()
        enriched["iso"] = iso_date(date)
        enriched["mag_class"] = magnitude_class(row.get("representative_vmax", ""))
        enriched["new_non_alpha_beta"] = "yes" if row.get("in_alpha_beta_layer") == "no" else "no"
        output.append(enriched)

        proper = (row.get("proper") or "").strip()
        if proper:
            proper_to_date.setdefault(proper, date.isoformat())
        bayer = (row.get("bayer") or "").strip()
        con = (row.get("con") or "").strip()
        if bayer and con:
            # Normalize HYG spelling such as Bet-1 to the Bayer regression key Bet1.
            bayer_to_date.setdefault((bayer.replace("-", ""), con), date.isoformat())

    # Run every historical regression object that exists in this bright-star layer.
    failures = []
    checked = 0
    for name, expected in REGRESSION.items():
        if name in REGRESSION_BAYER:
            actual = bayer_to_date.get(REGRESSION_BAYER[name])
        else:
            actual = proper_to_date.get(name)
        if actual is None:
            continue
        checked += 1
        if actual != expected:
            failures.append((name, expected, actual))
    if failures:
        for name, expected, actual in failures:
            print(f"FAIL {name}: expected {expected}, got {actual}")
        raise SystemExit(f"Bright-star best-visibility regression failed: {len(failures)}/{checked}")

    fieldnames = list(rows[0].keys()) + [
        "best_instant_utc", "best_date", "iso", "mag_class", "new_non_alpha_beta"
    ]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output)

    new_rows = sum(r["new_non_alpha_beta"] == "yes" for r in output)
    print(f"Bright-star visibility regression: {checked}/{checked} PASS")
    print(f"Dated bright-star systems: {len(output)}")
    print(f"New non-alpha/beta systems: {new_rows}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
