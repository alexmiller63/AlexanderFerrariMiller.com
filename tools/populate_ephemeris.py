#!/usr/bin/env python3
"""Populate weekly Star Almanack Solar-System ephemerides from JPL Horizons."""
from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HORIZONS_API = "https://ssd.jpl.nasa.gov/api/horizons.api"
SIGNS = "♈♉♊♋♌♍♎♏♐♑♒♓"

TARGETS = [
    ("☉ Sun", "sun", "10"),
    ("☽ Moon", "moon", "301"),
    ("☿ Mercury", "mercury", "199"),
    ("♀ Venus", "venus", "299"),
    ("♂ Mars", "mars", "499"),
    ("♃ Jupiter", "jupiter", "599"),
    ("♄ Saturn", "saturn", "699"),
    ("⚳ Ceres", "ceres", "1;"),
    ("♅ Uranus", "uranus", "799"),
    ("♆ Neptune", "neptune", "899"),
    ("♇ Pluto", "pluto", "999"),
]

VISIBILITY_GLYPHS = {
    "naked_eye": '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/eye.svg" alt="Naked eye" aria-label="Naked eye">',
    "binoculars": '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/binoculars.svg" alt="Binoculars" aria-label="Binoculars">',
    "telescope": '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/telescope.svg" alt="Telescope" aria-label="Telescope">',
    "near_sun": '<span class="text-symbol" role="img" aria-label="Near Sun — not currently observable" title="Near Sun — not currently observable">☉</span>',
}


def week_count(year):
    return date(year, 12, 28).isocalendar().week


def symbol_html(glyph):
    """Render a solar-system or zodiac glyph independently from its label text."""
    return f'<span class="ephemeris-symbol">{glyph}&#xfe0e;</span>'


def target_heading(display):
    glyph, name = display.split(" ", 1)
    return f"{symbol_html(glyph)} {name}"


def horizons_ephemeris(year, command):
    count = week_count(year)
    first = date.fromisocalendar(year, 1, 1)
    last = date.fromisocalendar(year, count, 1)
    params = {
        "format": "json",
        "COMMAND": f"'{command}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",
        "START_TIME": f"'{first.isoformat()} 00:00'",
        "STOP_TIME": f"'{(last + timedelta(days=1)).isoformat()} 00:00'",
        "STEP_SIZE": "'7 d'",
        "QUANTITIES": "'9,23,31'",
        "CSV_FORMAT": "'YES'",
        "ANG_FORMAT": "'DEG'",
        "CAL_FORMAT": "'CAL'",
        "TIME_DIGITS": "'SECONDS'",
    }
    req = urllib.request.Request(
        HORIZONS_API + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "Star-Almanack/ephemeris"},
    )
    payload = json.load(urllib.request.urlopen(req, timeout=90))
    text = payload.get("result", "")
    lines = text.splitlines()
    header_line = next(x for x in lines if "ObsEcLon" in x and "ObsEcLat" in x)
    header = [x.strip() for x in next(csv.reader([header_line]))]

    def column(*names):
        for name in names:
            if name in header:
                return header.index(name)
        return None

    lon_i = column("ObsEcLon")
    lat_i = column("ObsEcLat")
    mag_i = column("APmag", "T-mag")
    elong_i = column("S-O-T")
    values = []
    for line in lines[lines.index("$$SOE") + 1 : lines.index("$$EOE")]:
        if not line.strip():
            continue
        row = next(csv.reader([line]))

        def number(index):
            if index is None or row[index].strip() in ("", "n.a."):
                return None
            return float(row[index].strip())

        values.append((number(lon_i), number(lat_i), number(mag_i), number(elong_i)))
    if len(values) != count:
        raise RuntimeError(
            f"Expected {count} weekly rows for {year} target {command}, found {len(values)}"
        )
    return values


def zodiac(longitude):
    minutes = int(round((longitude % 360) * 60)) % (360 * 60)
    sign, within = divmod(minutes, 1800)
    degree, minute = divmod(within, 60)
    return f"{symbol_html(SIGNS[sign])} {degree}°{minute:02d}′"


def beta(latitude):
    sign = "+" if latitude >= 0 else "−"
    minutes = int(round(abs(latitude) * 60))
    degree, minute = divmod(minutes, 60)
    return f"β {sign}{degree}°{minute:02d}′"


def current_visibility(magnitude, elongation):
    """Return the current observing status from magnitude and solar elongation."""
    if elongation is not None and elongation < 20.0:
        return "near_sun"
    if magnitude is None or elongation is None:
        return None
    if magnitude <= 3.5:
        return "naked_eye"
    if magnitude <= 7.5:
        return "binoculars"
    return "telescope"


def visibility_html(magnitude, elongation):
    aid = current_visibility(magnitude, elongation)
    return VISIBILITY_GLYPHS[aid] if aid else ""


def render_ephemeris(monday, values):
    primary = TARGETS[:7]
    extended = TARGETS[7:]

    def table(columns, show_visibility=True, extra_class=""):
        headers = "".join(f"<th>{target_heading(display)}</th>" for display, _, _ in columns)
        positions = "".join(
            f"<td>{values[key][0]}<br><small>{values[key][1]}</small></td>"
            for _, key, _ in columns
        )
        rows = "<tr>" + positions + "</tr>"
        if show_visibility:
            rows += (
                f'<tr class="ephemeris-visibility-label"><th colspan="{len(columns)}" scope="rowgroup">Observing</th></tr>'
                + '<tr class="ephemeris-visibility" aria-label="Observing">'
                + "".join(f"<td>{values[key][2]}</td>" for _, key, _ in columns)
                + "</tr>"
            )
        classes = "ephemeris" + (f" {extra_class}" if extra_class else "")
        return (
            f'<table class="{classes}"><thead><tr>'
            + headers
            + "</tr></thead><tbody>"
            + rows
            + "</tbody></table>"
        )

    return (
        "<h3>Weekly Solar-System Ephemeris</h3>"
        + f'<p><strong>Snapshot:</strong> {monday.strftime("%B")} {monday.day}, {monday.year} · 00:00 UTC</p>'
        + "<p><strong>Naked Eye</strong></p>"
        + table(primary)
        + "<p><strong>Extended targets:</strong></p>"
        + table(extended, extra_class="extended-ephemeris")
        + '<p class="ephemeris-note"><strong>β</strong> = ecliptic latitude (+ north, − south). Observing combines visual magnitude with solar elongation. <span class="text-symbol">☉</span> = Near Sun — not currently observable.</p>'
    )


EPHEMERIS_TABLE = r'<table(?:\s+class="[^"]*ephemeris[^"]*")?>.*?</table>'
EPHEMERIS_BLOCK = re.compile(
    r'<h3>Weekly Solar-System Ephemeris</h3>\s*'
    r'<p><strong>Snapshot:</strong>.*?</p>\s*'
    r'(?:<p><strong>Naked Eye</strong></p>\s*)?'
    + EPHEMERIS_TABLE
    + r'\s*<p><strong>Extended targets:</strong></p>\s*'
    + EPHEMERIS_TABLE
    + r'\s*(?:<p class="ephemeris-note">.*?</p>)?',
    re.DOTALL,
)
CALENDAR_BLOCK = re.compile(
    r'(<h3>Calendar</h3>\s*<table\s+class="calendar">.*?</table>)', re.DOTALL
)


def put_ephemeris(text, replacement, path):
    """Replace a published ephemeris, or add one to a placeholder week after its calendar."""
    new, count = EPHEMERIS_BLOCK.subn(lambda _: replacement, text, count=1)
    if count == 1:
        return new

    new, count = CALENDAR_BLOCK.subn(
        lambda match: match.group(1) + replacement, text, count=1
    )
    if count == 1:
        return new

    raise RuntimeError(
        f"Could not locate either an ephemeris block or calendar insertion point in {path.relative_to(ROOT)}"
    )


def update_year(year):
    count = week_count(year)
    generated = {}
    for _, key, command in TARGETS:
        print(f"Fetching {year} {key} from JPL Horizons")
        generated[key] = horizons_ephemeris(year, command)

    changed = 0
    for week in range(1, count + 1):
        monday = date.fromisocalendar(year, week, 1)
        values = {
            key: (
                zodiac(generated[key][week - 1][0]),
                beta(generated[key][week - 1][1]),
                visibility_html(
                    generated[key][week - 1][2], generated[key][week - 1][3]
                ),
            )
            for _, key, _ in TARGETS
        }
        replacement = render_ephemeris(monday, values)
        for base in (ROOT / "almanack", ROOT / "Star-Almanack-Repo" / "site"):
            path = base / str(year) / f"W{week:02d}" / "index.html"
            text = path.read_text(encoding="utf-8")
            new = put_ephemeris(text, replacement, path)
            if new != text:
                path.write_text(new, encoding="utf-8")
                changed += 1
    return changed


def parse_years():
    parser = argparse.ArgumentParser(
        description="Populate weekly Solar-System ephemeris for one or more ISO years."
    )
    parser.add_argument("years", nargs="+", type=int, help="ISO week-years to populate")
    args = parser.parse_args()
    years = list(dict.fromkeys(args.years))
    for year in years:
        if not 1900 <= year <= 2100:
            parser.error(f"YEAR must be between 1900 and 2100: {year}")
    return years


def main():
    years = parse_years()
    total = 0
    for year in years:
        changed = update_year(year)
        print(f"Updated {changed} weekly pages for {year}")
        total += changed
    print(f"Updated {total} weekly pages total")


if __name__ == "__main__":
    main()
