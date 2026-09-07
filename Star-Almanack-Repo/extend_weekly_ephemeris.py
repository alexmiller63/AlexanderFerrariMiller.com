#!/usr/bin/env python3
"""Extend the 2026 weekly ephemeris with Uranus, Neptune, Ceres, and Pluto.

The existing Sun-through-Saturn longitude values are preserved. The historical
source is split between almanack.md and weekly-ephemeris-2026.csv; this program
merges those sources into a complete 53-week CSV and adds observer-oriented
outer-body positions from NASA/JPL Horizons.

Horizons observer quantity 31 supplies apparent, geocentric, ecliptic-of-date
longitude and latitude, sampled at the Almanack standard epoch: Monday 00:00
UTC. Longitude is rendered in zodiac-sign notation and beta (β) as signed
ecliptic latitude, both rounded to the nearest arcminute.
"""
from __future__ import annotations

import csv
import json
import re
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
CSV_PATH = ROOT / "weekly-ephemeris-2026.csv"
ALMANACK_PATH = ROOT / "almanack.md"
HORIZONS_API = "https://ssd.jpl.nasa.gov/api/horizons.api"
TARGETS = {"uranus": "799", "neptune": "899", "ceres": "1;", "pluto": "999"}
SIGNS = "♈♉♊♋♌♍♎♏♐♑♒♓"
BASE_FIELDS = ["iso_week", "monday_utc", "sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn"]


def horizons_ecliptic(command: str) -> list[tuple[float, float]]:
    params = {
        "format": "json", "COMMAND": f"'{command}'", "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'OBSERVER'", "CENTER": "'500@399'",
        "START_TIME": "'2025-12-29 00:00'", "STOP_TIME": "'2026-12-29 00:00'",
        "STEP_SIZE": "'7 d'", "QUANTITIES": "'31'", "CSV_FORMAT": "'YES'",
        "ANG_FORMAT": "'DEG'", "CAL_FORMAT": "'CAL'", "TIME_DIGITS": "'SECONDS'",
    }
    url = HORIZONS_API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "Star-Almanack/2026"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    text = payload.get("result", "")
    if "$$SOE" not in text or "$$EOE" not in text:
        raise RuntimeError(f"Horizons returned no ephemeris for {command}: {text[:500]}")
    lines = text.splitlines()
    header_line = next((line for line in lines if "ObsEcLon" in line and "ObsEcLat" in line), None)
    if not header_line:
        raise RuntimeError(f"Could not find ObsEcLon/ObsEcLat headers for {command}")
    header = [h.strip() for h in next(csv.reader([header_line]))]
    lon_index, lat_index = header.index("ObsEcLon"), header.index("ObsEcLat")
    values = []
    for line in lines[lines.index("$$SOE") + 1:lines.index("$$EOE")]:
        if line.strip():
            row = next(csv.reader([line]))
            values.append((float(row[lon_index].strip()), float(row[lat_index].strip())))
    if len(values) != 53:
        raise RuntimeError(f"Expected 53 weekly Horizons rows for {command}, found {len(values)}")
    return values


def rows_from_almanack() -> dict[str, dict[str, str]]:
    text = ALMANACK_PATH.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^## ISO 2026-W(\d{2})\s*$", text))
    result = {}
    for i, match in enumerate(matches):
        week = int(match.group(1)); end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section = text[match.start():end]
        table = re.search(r"(?ms)\|\s*☉ Sun\s*\|\s*☽ Moon\s*\|\s*☿ Mercury\s*\|\s*♀ Venus\s*\|\s*♂ Mars\s*\|\s*♃ Jupiter\s*\|\s*♄ Saturn\s*\|\s*\n\s*\|[^\n]+\|\s*\n\s*\|\s*([^\n]+)\s*\|\s*(?:\n|$)", section)
        if not table: raise RuntimeError(f"Could not recover base ephemeris for 2026-W{week:02d}")
        values = [cell.strip() for cell in table.group(1).split("|")]
        if len(values) != 7: raise RuntimeError(f"Expected 7 base values for 2026-W{week:02d}")
        monday = date.fromisocalendar(2026, week, 1)
        row = {"iso_week": f"2026-W{week:02d}", "monday_utc": monday.isoformat()}
        for field, value in zip(BASE_FIELDS[2:], values): row[field] = value
        result[row["iso_week"]] = row
    return result


def zodiac(x: float) -> str:
    total = int(round((x % 360) * 60)) % 21600; sign, within = divmod(total, 1800); deg, minute = divmod(within, 60)
    return f"{SIGNS[sign]} {deg}°{minute:02d}′"


def beta(x: float) -> str:
    sign = "+" if x >= 0 else "−"; total = int(round(abs(x) * 60)); deg, minute = divmod(total, 60)
    return f"β {sign}{deg}°{minute:02d}′"


def main() -> None:
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        current_rows = list(csv.DictReader(f)); current_fields = list(current_rows[0].keys()) if current_rows else []
    if current_fields[:9] != BASE_FIELDS: raise SystemExit(f"Unexpected weekly ephemeris columns: {current_fields}")
    combined = rows_from_almanack()
    for row in current_rows: combined[row["iso_week"]] = {key: row[key] for key in BASE_FIELDS}
    expected = [f"2026-W{week:02d}" for week in range(1, 54)]
    missing = [key for key in expected if key not in combined]
    if missing: raise SystemExit(f"Missing base ephemeris weeks after source merge: {missing}")
    rows = [combined[key] for key in expected]
    generated = {name: horizons_ecliptic(command) for name, command in TARGETS.items()}
    for i, row in enumerate(rows):
        for name in TARGETS:
            lon, lat = generated[name][i]; row[name] = zodiac(lon); row[name + "_beta"] = beta(lat)
    fields = BASE_FIELDS + [item for name in TARGETS for item in (name, name + "_beta")]
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    print("Extended weekly-ephemeris-2026.csv: 53 weeks × Uranus, Neptune, Ceres, Pluto with beta from JPL Horizons")

if __name__ == "__main__": main()
