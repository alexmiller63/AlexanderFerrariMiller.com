#!/usr/bin/env python3
"""Read Star Almanack's preserved weekly planetary-position data.

This module is deliberately data-layer only. It never calls an external
ephemeris service. Presentation generators (Ephemeris, Planet Finder,
Sky Notes, artwork) should consume the same preserved Star Almanack data.

The current preserved table records geocentric tropical ecliptic longitude
for each ISO-week Monday at 00:00 UTC. A requested year without a preserved
table is an error; consumers must not silently substitute another source.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Historical"

SIGN_BASE = {
    "♈": 0.0, "♉": 30.0, "♊": 60.0, "♋": 90.0,
    "♌": 120.0, "♍": 150.0, "♎": 180.0, "♏": 210.0,
    "♐": 240.0, "♑": 270.0, "♒": 300.0, "♓": 330.0,
}
POSITION_RE = re.compile(r"^\s*([♈♉♊♋♌♍♎♏♐♑♒♓])\s*(\d+)°(\d+)′\s*$")

PLANET_COLUMNS = (
    "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune"
)


def parse_zodiac_longitude(value: str) -> float:
    """Convert reader-facing sign/degree/arcminute text to 0..360 degrees."""
    match = POSITION_RE.match(value or "")
    if not match:
        raise ValueError(f"Invalid Star Almanack zodiac position: {value!r}")
    sign, degree, minute = match.groups()
    degree_i = int(degree)
    minute_i = int(minute)
    if not 0 <= degree_i < 30 or not 0 <= minute_i < 60:
        raise ValueError(f"Out-of-range Star Almanack zodiac position: {value!r}")
    return (SIGN_BASE[sign] + degree_i + minute_i / 60.0) % 360.0


def preserved_ephemeris_path(year: int) -> Path:
    return SOURCE_ROOT / f"weekly-ephemeris-{year}.csv"


def load_weekly_longitudes(year: int) -> dict[int, dict[str, float]]:
    """Return {iso_week: {body: geocentric tropical longitude_deg}}."""
    path = preserved_ephemeris_path(year)
    if not path.exists():
        raise RuntimeError(
            f"Missing preserved Star Almanack planetary data: {path.relative_to(ROOT)}. "
            "Generate and validate the calculation-layer data first; presentation "
            "generators must not fetch or substitute an external ephemeris."
        )

    rows: dict[int, dict[str, float]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"iso_week", *PLANET_COLUMNS}
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise RuntimeError(
                f"{path.relative_to(ROOT)} is missing columns: {', '.join(sorted(missing))}"
            )

        for row in reader:
            key = row["iso_week"]
            match = re.fullmatch(rf"{year}-W(\d{{2}})", key or "")
            if not match:
                raise RuntimeError(
                    f"Unexpected ISO week {key!r} in {path.relative_to(ROOT)}"
                )
            week = int(match.group(1))
            if week in rows:
                raise RuntimeError(
                    f"Duplicate ISO week {key} in {path.relative_to(ROOT)}"
                )
            rows[week] = {
                body: parse_zodiac_longitude(row[body]) for body in PLANET_COLUMNS
            }

    if not rows:
        raise RuntimeError(f"No planetary rows in {path.relative_to(ROOT)}")
    return rows
