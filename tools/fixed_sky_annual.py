#!/usr/bin/env python3
"""Annual fixed-sky visibility coverage.

The astronomical calculation year is one tropical year: one First Point of
Aries (March equinox) crossing through the next.  Results are persisted so a
weekly generator consumes an already-calculated annual dataset instead of
recomputing the fixed-object population.

JDTDB is the canonical instant.  UTC is retained only as publication metadata.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

import yaml
from skyfield import almanac
from skyfield.searchlib import find_minima

from almanack_time import AstroInstant, datetime_to_jd_utc
from star_almanack_ephemeris import StarAlmanackEphemeris

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "database" / "fixed-sky-annual-coverage.json"
FIXED_OBJECTS = ROOT / "fixed-objects.yaml"
SCHEMA_VERSION = 2
OBSERVING_HOUR_ANGLE_HOURS = 9.0


def _astro_instant(t) -> AstroInstant:
    jd_tdb = float(t.tdb)
    jd_utc = datetime_to_jd_utc(t.utc_datetime())
    return AstroInstant(
        jd_tdb=jd_tdb,
        tdb_minus_utc_seconds=(jd_tdb - jd_utc) * 86400.0,
    )


def _coverage_boundary(eph: StarAlmanackEphemeris, year: int):
    t0 = eph.ts.utc(year, 3, 1)
    t1 = eph.ts.utc(year, 4, 1)
    seasons = almanac.seasons(eph.planets)
    times, values = almanac.find_discrete(t0, t1, seasons)
    matches = [t for t, value in zip(times, values) if int(value) == 0]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one March equinox for {year}, found {len(matches)}"
        )
    return _astro_instant(matches[0])


def coverage_interval(eph: StarAlmanackEphemeris, start_year: int) -> dict:
    start = _coverage_boundary(eph, start_year)
    end = _coverage_boundary(eph, start_year + 1)
    if not start.jd_tdb < end.jd_tdb:
        raise RuntimeError(f"Invalid Aries coverage interval for {start_year}")
    return {
        "coverage_year": start_year,
        "start_jd_tdb": start.jd_tdb,
        "start_utc": start.utc_datetime().isoformat().replace("+00:00", "Z"),
        "end_jd_tdb": end.jd_tdb,
        "end_utc": end.utc_datetime().isoformat().replace("+00:00", "Z"),
        "basis": "First Point of Aries to First Point of Aries",
    }


def _hour_distance(hours, target: float):
    return abs((hours - target + 12.0) % 24.0 - 12.0)


def _best_visibility(eph: StarAlmanackEphemeris, start, end, ra_h: float):
    target = (float(ra_h) - OBSERVING_HOUR_ANGLE_HOURS) % 24.0
    earth = eph.earth
    sun = eph.sun

    def distance(t):
        apparent = earth.at(t).observe(sun).apparent()
        ra, _, _ = apparent.radec(epoch="date")
        return _hour_distance(ra.hours, target)

    distance.step_days = 30.0
    t0 = eph.ts.tdb(jd=start.jd_tdb)
    t1 = eph.ts.tdb(jd=end.jd_tdb)
    times, values = find_minima(t0, t1, distance)
    if len(times) != 1:
        raise RuntimeError(
            f"Expected exactly one annual best-visibility minimum for RA {ra_h}, "
            f"found {len(times)}"
        )
    instant = _astro_instant(times[0])
    if not start.jd_tdb <= instant.jd_tdb < end.jd_tdb:
        raise RuntimeError("Best-visibility instant escaped coverage interval")
    return instant


def _read_csv(name: str):
    with (ROOT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _messier_rows():
    data = yaml.safe_load(FIXED_OBJECTS.read_text(encoding="utf-8")) or {}
    fields = (data.get("schema") or {}).get("messier") or []
    return [dict(zip(fields, row)) for row in data.get("messier") or []]


def _source_records():
    import populate_fixed_sky as fixed
    records = []

    for row in _read_csv("expanded-bayer-visibility-2026.csv"):
        bayer = (row.get("bayer") or "").strip()
        con = (row.get("con") or "").strip()
        if bayer and con and row.get("ra_h"):
            fixed_id = None
            for namespace, value in (
                ("hip", row.get("hip")),
                ("hd", row.get("hd")),
                ("bayer", fixed.display_bayer(row)),
            ):
                value = (value or "").strip()
                if value:
                    fixed_id = fixed.FIXED_OBJECT_IDS.get((namespace, value.lower()))
                    if fixed_id is not None:
                        break
            if fixed_id is None:
                raise RuntimeError(
                    f"No permanent fixed-object ID for expanded Bayer {bayer}:{con}"
                )
            records.append(("expanded-bayer", f"{bayer}:{con}", float(row["ra_h"]), fixed_id))

    for row in _read_csv("bright-star-visibility-2026.csv"):
        if (row.get("new_non_alpha_beta") or "").lower() != "yes":
            continue
        key = (row.get("proper") or "").strip() or (
            (row.get("bayer") or "").strip() + ":" + (row.get("con") or "").strip()
        )
        if key and row.get("ra_h"):
            fixed_id = None
        for namespace, value in (("hip", row.get("hip")), ("hd", row.get("hd"))):
            value = (value or "").strip()
            if value:
                fixed_id = fixed.FIXED_OBJECT_IDS.get((namespace, value.lower()))
                if fixed_id is not None:
                    break
        if fixed_id is None:
            raise RuntimeError(f"No permanent fixed-object ID for bright star {key}")
        records.append(("bright-star", key, float(row["ra_h"]), fixed_id))

    for row in _messier_rows():
        if row.get("id") and row.get("ra_h"):
            identity = str(row["id"]).strip()
            fixed_id = fixed.catalog_target_fixed_object_id("messier", identity)
            if fixed_id is None:
                continue
            records.append(("messier", identity, float(row["ra_h"]), fixed_id))

    return records


def _load_table():
    if not TABLE.exists():
        return {"schema_version": SCHEMA_VERSION, "coverage": []}
    data = json.loads(TABLE.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError(f"Unsupported fixed-sky coverage schema in {TABLE}")
    return data


def _write_table(data):
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    TABLE.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def ensure_coverage(start_year: int, eph: StarAlmanackEphemeris | None = None) -> dict:
    eph = eph or StarAlmanackEphemeris()
    data = _load_table()
    existing = {
        int(row["coverage_year"]): row
        for row in data.get("coverage", [])
    }
    if start_year in existing:
        return existing[start_year]

    interval = coverage_interval(eph, start_year)
    objects = []
    for source, key, ra_h, fixed_id in _source_records():
        instant = _best_visibility(eph, 
            AstroInstant(
                interval["start_jd_tdb"],
                0.0,
            ),
            AstroInstant(
                interval["end_jd_tdb"],
                0.0,
            ),
            ra_h,
        )
        publication = instant.publication_utc()
        best_day = (publication + dt.timedelta(hours=12)).date()
        objects.append({
            "source": source,
            "key": key,
            "fixed_object_id": fixed_id,
            "ra_h": ra_h,
            "best_jd_tdb": instant.jd_tdb,
            "best_utc": instant.utc_datetime().isoformat().replace("+00:00", "Z"),
            "best_date": best_day.isoformat(),
            "iso": f"{best_day.isocalendar().year}-W{best_day.isocalendar().week:02d}",
        })

    interval["object_count"] = len(objects)
    interval["objects"] = objects
    existing[start_year] = interval
    data["coverage"] = [existing[key] for key in sorted(existing)]
    _write_table(data)
    return interval


def coverage_years_for_iso_year(iso_year: int) -> tuple[int, int]:
    return iso_year - 1, iso_year


def occurrences_for_iso_year(iso_year: int):
    data = _load_table()
    result = {}
    available = {
        int(row["coverage_year"]): row
        for row in data.get("coverage", [])
    }
    for coverage_year in coverage_years_for_iso_year(iso_year):
        interval = available.get(coverage_year)
        if interval is None:
            raise RuntimeError(
                f"Missing fixed-sky Aries-to-Aries coverage row {coverage_year}; "
                "run tools/fixed_sky_annual.py before the weekly generator"
            )
        for obj in interval["objects"]:
            day = dt.date.fromisoformat(obj["best_date"])
            if day.isocalendar().year != iso_year:
                continue
            result[(obj["source"], obj["key"])] = obj
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build missing tropical Aries-to-Aries fixed-sky coverage rows."
    )
    parser.add_argument("start_year", type=int)
    parser.add_argument("end_year", type=int)
    args = parser.parse_args()
    eph = StarAlmanackEphemeris()
    for year in range(args.start_year, args.end_year + 1):
        ensure_coverage(year, eph)
    print(f"Fixed-sky annual coverage complete: {args.start_year} through {args.end_year}")
