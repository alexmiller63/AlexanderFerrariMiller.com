#!/usr/bin/env python3
"""Build the annual fixed-sky astronomical crib sheet.

One coverage row spans one tropical Aries-to-Aries interval. Each active fixed
object gets one best-visibility JDTDB instant in that interval. The table is
the reusable astronomy layer consumed by weekly Calendar generation.

JDTDB is canonical. UTC date/time and ISO week are derived publication fields.
The Aries boundaries come from the same locally calculated apparent
geocentric ecliptic longitude engine used by the Calendar.
"""
from __future__ import annotations

import csv
import datetime as dt
import sys
from pathlib import Path

import populate_calendar as calendar
import populate_fixed_sky as fixed
from almanack_time import AstroInstant
from star_almanack_astronomy import _best_time_for_solar_ra

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "fixed-sky-annual.csv"


def aries_boundaries(year: int) -> tuple[AstroInstant, AstroInstant]:
    start_samples = calendar.source_longitudes(
        "sun", dt.date(year, 3, 18), dt.date(year, 3, 22)
    )
    end_samples = calendar.source_longitudes(
        "sun", dt.date(year + 1, 3, 18), dt.date(year + 1, 3, 22)
    )
    starts = [event for event in calendar.longitude_events(start_samples, 360.0)
              if abs(event[1]) < 1.0e-12]
    ends = [event for event in calendar.longitude_events(end_samples, 360.0)
            if abs(event[1]) < 1.0e-12]
    if len(starts) != 1 or len(ends) != 1:
        raise RuntimeError(
            f"Expected one Aries crossing for {year} and {year + 1}; "
            f"found {len(starts)} and {len(ends)}"
        )
    return starts[0][0], ends[0][0]


def best_visibility(row: dict[str, str], start: AstroInstant, end: AstroInstant):
    target = (float(row["ra_h"]) - 9.0) % 24.0
    start_dt = start.utc_datetime().replace(tzinfo=None)
    end_dt = end.utc_datetime().replace(tzinfo=None)
    instant = _best_time_for_solar_ra(target, start_dt, end_dt)
    return instant


def canonical_rows(year: int):
    bayer = fixed.redated(fixed.read_csv("expanded-bayer-visibility-2026.csv"), year)
    bright = fixed.redated(fixed.read_csv("bright-star-visibility-2026.csv"), year)
    messier = fixed.redated_preserving_2026_phase(
        fixed.read_csv("messier-visibility-2026.csv"), year
    )
    rows = []

    bayer_targets = {}
    for row in bayer:
        identity = fixed.display_bayer(row).strip().lower()
        if not identity:
            continue
        current = bayer_targets.get(identity)
        if current is None or (
            not (current.get("proper") or "").strip()
            and (row.get("proper") or "").strip()
        ):
            bayer_targets[identity] = row

    for row in bayer_targets.values():
        rows.append(("fixed_star", fixed.star_event(row), row))

    for row in bright:
        if row.get("new_non_alpha_beta", "").lower() == "yes":
            rows.append(("fixed_star", fixed.star_event(row), row))

    for row in messier:
        identity = row["messier"].strip()
        catalog = fixed.MESSIER_CATALOG.get(identity)
        if catalog is None:
            raise RuntimeError(f"Missing {identity} from fixed-object catalog")
        rows.append(("deep_sky", None, {
            "identity": identity,
            "ra_h": str(catalog.get("ra_h") or row.get("ra_h") or ""),
            "fixed_object_id": str(fixed.catalog_target_fixed_object_id("messier", identity) or ""),
        }))
    return rows


def build(year: int):
    start, end = aries_boundaries(year)
    output = []
    for object_type, event, source in canonical_rows(year):
        if object_type == "fixed_star":
            fixed_id = event.fixed_object_id
            identity = source.get("proper") or fixed.display_bayer(source)
            instant = best_visibility(source, start, end)
        else:
            fixed_id = int(source["fixed_object_id"]) if source["fixed_object_id"] else None
            if fixed_id is None:
                raise RuntimeError(f"No fixed-object ID for Messier {source['identity']}")
            identity = source["identity"]
            if not source["ra_h"]:
                raise RuntimeError(f"No RA for Messier {identity}")
            instant = best_visibility(source, start, end)

        if not start.utc_datetime() <= instant.replace(tzinfo=dt.timezone.utc) < end.utc_datetime():
            raise RuntimeError(
                f"Best visibility for {identity} falls outside {year} Aries-to-Aries coverage"
            )

        astro = dt.datetime_to_julian if False else None
        # Reconstruct the same canonical JDTDB instant from the UTC result using
        # Skyfield's time conversion through the existing ephemeris layer.
        ephem = calendar._source_engine()
        t = ephem.ts.from_datetime(instant.replace(tzinfo=dt.timezone.utc))
        canonical = ephem._instant_from_skyfield(t)
        publication = canonical.publication_utc()
        output.append({
            "coverage_year": str(year),
            "coverage_start_jd_tdb": f"{start.jd_tdb:.12f}",
            "coverage_end_jd_tdb": f"{end.jd_tdb:.12f}",
            "coverage_start_utc": start.utc_datetime().isoformat(),
            "coverage_end_utc": end.utc_datetime().isoformat(),
            "fixed_object_id": "" if fixed_id is None else str(fixed_id),
            "object_type": object_type,
            "identity": identity,
            "best_visibility_jd_tdb": f"{canonical.jd_tdb:.12f}",
            "best_visibility_utc": publication.isoformat(),
            "best_date": publication.date().isoformat(),
            "iso": f"{publication.date().isocalendar().year}-W{publication.date().isocalendar().week:02d}",
        })
    return output


def main():
    years = tuple(int(value) for value in sys.argv[1:]) if len(sys.argv) > 1 else (2026,)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "coverage_year", "coverage_start_jd_tdb", "coverage_end_jd_tdb",
        "coverage_start_utc", "coverage_end_utc", "fixed_object_id",
        "object_type", "identity", "best_visibility_jd_tdb",
        "best_visibility_utc", "best_date", "iso",
    ]
    mode = "w"
    with OUTPUT.open(mode, newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for year in years:
            for row in build(year):
                writer.writerow(row)
            print(f"{year}: annual fixed-sky coverage written to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
