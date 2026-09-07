#!/usr/bin/env python3
"""Populate 2025 and 2027 weekly Solar-System ephemerides from JPL Horizons.

The tool samples apparent geocentric ecliptic-of-date longitude and latitude
at each ISO Monday 00:00 UTC. Longitude is rendered in traditional zodiac
notation; beta (β) is rendered as signed ecliptic latitude.
"""
from __future__ import annotations

import csv
import json
import re
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HORIZONS_API = "https://ssd.jpl.nasa.gov/api/horizons.api"
YEARS = (2025, 2027)
SIGNS = "♈♉♊♋♌♍♎♏♐♑♒♓"
TARGETS = [
    ("☉ Sun", "sun", "10"),
    ("☽ Moon", "moon", "301"),
    ("☿ Mercury", "mercury", "199"),
    ("♀ Venus", "venus", "299"),
    ("♂ Mars", "mars", "499"),
    ("♃ Jupiter", "jupiter", "599"),
    ("♄ Saturn", "saturn", "699"),
    ("♅ Uranus", "uranus", "799"),
    ("♆ Neptune", "neptune", "899"),
    ("⚳ Ceres", "ceres", "1;"),
    ("♇ Pluto", "pluto", "999"),
]


def week_count(year: int) -> int:
    return date(year, 12, 28).isocalendar().week


def horizons_ecliptic(year: int, command: str) -> list[tuple[float, float]]:
    count = week_count(year)
    first = date.fromisocalendar(year, 1, 1)
    last = date.fromisocalendar(year, count, 1)
    params = {
        "format": "json", "COMMAND": f"'{command}'", "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'OBSERVER'", "CENTER": "'500@399'",
        "START_TIME": f"'{first.isoformat()} 00:00'",
        "STOP_TIME": f"'{(last + timedelta(days=1)).isoformat()} 00:00'",
        "STEP_SIZE": "'7 d'", "QUANTITIES": "'31'", "CSV_FORMAT": "'YES'",
        "ANG_FORMAT": "'DEG'", "CAL_FORMAT": "'CAL'", "TIME_DIGITS": "'SECONDS'",
    }
    url = HORIZONS_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Star-Almanack/2025-2027"})
    with urllib.request.urlopen(req, timeout=90) as response:
        payload = json.load(response)
    text = payload.get("result", "")
    if "$$SOE" not in text or "$$EOE" not in text:
        raise RuntimeError(f"Horizons returned no ephemeris for {year} target {command}: {text[:500]}")
    lines = text.splitlines()
    header_line = next((line for line in lines if "ObsEcLon" in line and "ObsEcLat" in line), None)
    if not header_line:
        raise RuntimeError(f"Could not find ObsEcLon/ObsEcLat headers for {year} target {command}")
    header = [h.strip() for h in next(csv.reader([header_line]))]
    lon_index = header.index("ObsEcLon")
    lat_index = header.index("ObsEcLat")
    start = lines.index("$$SOE") + 1
    stop = lines.index("$$EOE")
    values: list[tuple[float, float]] = []
    for line in lines[start:stop]:
        if not line.strip():
            continue
        row = next(csv.reader([line]))
        values.append((float(row[lon_index].strip()), float(row[lat_index].strip())))
    if len(values) != count:
        raise RuntimeError(f"Expected {count} weekly rows for {year} target {command}, found {len(values)}")
    return values


def zodiac(longitude_deg: float) -> str:
    total_minutes = int(round((longitude_deg % 360.0) * 60.0)) % (360 * 60)
    sign_index, within = divmod(total_minutes, 30 * 60)
    degrees, minutes = divmod(within, 60)
    return f"{SIGNS[sign_index]} {degrees}°{minutes:02d}′"


def beta(latitude_deg: float) -> str:
    sign = "+" if latitude_deg >= 0 else "−"
    total_minutes = int(round(abs(latitude_deg) * 60.0))
    degrees, minutes = divmod(total_minutes, 60)
    return f"β {sign}{degrees}°{minutes:02d}′"


def render_ephemeris(monday: date, values: dict[str, tuple[str, str]]) -> str:
    primary = TARGETS[:7]
    extended = TARGETS[7:]

    def table(columns: list[tuple[str, str, str]]) -> str:
        return (
            '<table class="ephemeris"><thead><tr>'
            + ''.join(f'<th>{display}</th>' for display, _key, _command in columns)
            + '</tr></thead><tbody><tr>'
            + ''.join(f'<td>{values[key][0]}<br><small>{values[key][1]}</small></td>' for _display, key, _command in columns)
            + '</tr></tbody></table>'
        )

    return (
        '<h3>Weekly Solar-System Ephemeris</h3>'
        f'<p><strong>Snapshot:</strong> {monday.strftime("%B")} {monday.day}, {monday.year} · 00:00 UTC</p>'
        + table(primary)
        + '<p><strong>Extended targets:</strong></p>'
        + table(extended)
        + '<p class="ephemeris-note"><strong>β</strong> = ecliptic latitude (+ north, − south).</p>'
    )


def update_year(year: int) -> int:
    count = week_count(year)
    generated: dict[str, list[tuple[float, float]]] = {}
    for _display, key, command in TARGETS:
        print(f"Fetching {year} {key} from JPL Horizons")
        generated[key] = horizons_ecliptic(year, command)

    pattern = re.compile(
        r'<h3>Weekly Solar-System Ephemeris</h3>'
        r'<p><strong>Snapshot:</strong>.*?</p>'
        r'<table class="ephemeris">.*?</table>'
        r'<p><strong>Extended targets:</strong></p>'
        r'<table class="ephemeris">.*?</table>'
        r'(?:<p class="ephemeris-note">.*?</p>)?', re.DOTALL,
    )

    changed = 0
    for week in range(1, count + 1):
        monday = date.fromisocalendar(year, week, 1)
        values = {key: (zodiac(generated[key][week - 1][0]), beta(generated[key][week - 1][1])) for _display, key, _command in TARGETS}
        replacement = render_ephemeris(monday, values)
        for base in (ROOT / "almanack", ROOT / "Star-Almanack-Repo" / "site"):
            path = base / str(year) / f"W{week:02d}" / "index.html"
            if not path.exists():
                raise RuntimeError(f"Missing weekly page: {path.relative_to(ROOT)}")
            text = path.read_text(encoding="utf-8")
            new_text, n = pattern.subn(lambda _m: replacement, text, count=1)
            if n != 1:
                raise RuntimeError(f"Could not locate ephemeris block in {path.relative_to(ROOT)}")
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                changed += 1
    return changed


def main() -> None:
    total = 0
    for year in YEARS:
        changed = update_year(year)
        print(f"Updated {changed} weekly page copies for {year}")
        total += changed
    print(f"Updated {total} weekly page copies total; 2026 was not touched")


if __name__ == "__main__":
    main()
