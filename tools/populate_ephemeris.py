#!/usr/bin/env python3
"""Populate weekly Star Almanack Solar-System ephemerides from local source kernels.

The weekly table is a civil-time presentation snapshot: each row is sampled at
Monday 00:00 UTC, then calculated locally from cached JPL/NAIF SPK source data.
No Horizons or other answer service is queried.
"""
from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from star_almanack_ephemeris import StarAlmanackEphemeris

ROOT = Path(__file__).resolve().parents[1]
SIGNS = "♈♉♊♋♌♍♎♏♐♑♒♓"

TARGETS = [
    ("☉ Sun", "sun", "sun"), ("☽ Moon", "moon", "moon"), ("☿ Mercury", "mercury", "mercury"),
    ("♀ Venus", "venus", "venus"), ("♂ Mars", "mars", "mars"), ("♃ Jupiter", "jupiter", "jupiter"),
    ("♄ Saturn", "saturn", "saturn"), ("⚳ Ceres", "ceres", "ceres"), ("♅ Uranus", "uranus", "uranus"),
    ("♆ Neptune", "neptune", "neptune"), ("♇ Pluto", "pluto", "pluto"),
]

# Weekly pages live at YEAR/WEEK/index.html. Use the portable relative asset
# path so the same generated HTML works both on the custom domain and on the
# repository-prefixed GitHub Pages deployment.
VISIBILITY_GLYPH_ROOT = "../../../assets/almanack/visibility-glyphs/masters/"
VISIBILITY_GLYPHS = {
    "naked_eye": f'<img class="visibility-glyph" src="{VISIBILITY_GLYPH_ROOT}eye.svg" alt="Naked eye" aria-label="Naked eye">',
    "binoculars": f'<img class="visibility-glyph" src="{VISIBILITY_GLYPH_ROOT}binoculars.svg" alt="Binoculars" aria-label="Binoculars">',
    "telescope": f'<img class="visibility-glyph" src="{VISIBILITY_GLYPH_ROOT}telescope.svg" alt="Telescope" aria-label="Telescope">',
    "near_sun": '<span class="text-symbol" role="img" aria-label="Near Sun — not currently observable" title="Near Sun — not currently observable">☉</span>',
}


def notation_toggle(target):
    return (
        f'<div class="bayer-toggle-wrap section-notation-toggle" data-notation-target="{target}">'
        '<div class="bayer-toggle" role="group" aria-label="Astronomical notation">'
        '<span class="bayer-toggle-label">Notation:</span>'
        '<button type="button" data-bayer-mode="greek" aria-pressed="true">Greek/Symbols</button>'
        '<button type="button" data-bayer-mode="latin" aria-pressed="false">Latin</button>'
        '<button type="button" data-bayer-mode="mixed" data-legacy-label="Mixed · Learner" aria-pressed="false">Mixed Learner</button>'
        '</div></div>'
    )


def week_count(year): return date(year, 12, 28).isocalendar().week

def symbol_html(glyph): return f'<span class="ephemeris-symbol">{glyph}&#xfe0e;</span>'

def target_heading(display):
    glyph, name = display.split(" ", 1)
    return f"{symbol_html(glyph)} {name}"


def computed_ephemeris(year: int, engine: StarAlmanackEphemeris | None = None):
    """Return locally calculated Monday-00:00-UTC samples for every target."""
    engine = engine or StarAlmanackEphemeris()
    count = week_count(year)
    generated = {key: [] for _, key, _ in TARGETS}
    for week in range(1, count + 1):
        monday = date.fromisocalendar(year, week, 1)
        for _, key, _ in TARGETS:
            sample = engine.sample(key, monday)
            generated[key].append((
                sample.longitude_deg,
                sample.latitude_deg,
                sample.magnitude,
                sample.elongation_deg,
            ))
    return generated


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
    if elongation is not None and elongation < 20.0: return "near_sun"
    if magnitude is None or elongation is None: return None
    if magnitude <= 3.5: return "naked_eye"
    if magnitude <= 7.5: return "binoculars"
    return "telescope"


def visibility_html(magnitude, elongation):
    aid = current_visibility(magnitude, elongation)
    return VISIBILITY_GLYPHS[aid] if aid else ""


def planet_finder(year, week):
    base = "finders"
    return (
        '<div class="planet-finder-strip w15-finder-strip">'
        f'<figure data-finder-mode="greek" class="is-active"><img src="{base}/planet-finder-greek-symbols.svg" alt="Planet Finder — Greek / Symbols"><figcaption>Greek / Symbols</figcaption></figure>'
        f'<figure data-finder-mode="latin"><img src="{base}/planet-finder-latin.svg" alt="Planet Finder — Latin"><figcaption>Latin</figcaption></figure>'
        f'<figure data-finder-mode="mixed"><img src="{base}/planet-finder-mixed-learner.svg" alt="Planet Finder — Mixed Learner"><figcaption>Mixed Learner</figcaption></figure>'
        '</div>'
    )


def render_ephemeris(monday, values):
    primary, extended = TARGETS[:7], TARGETS[7:]
    week = monday.isocalendar().week

    def table(columns, show_visibility=True, extra_class=""):
        headers = "".join(f"<th>{target_heading(display)}</th>" for display, _, _ in columns)
        positions = "".join(f"<td>{values[key][0]}<br><small>{values[key][1]}</small></td>" for _, key, _ in columns)
        rows = "<tr>" + positions + "</tr>"
        if show_visibility:
            rows += f'<tr class="ephemeris-visibility-label"><th colspan="{len(columns)}" scope="rowgroup">Observing</th></tr>'
            rows += '<tr class="ephemeris-visibility" aria-label="Observing">' + "".join(f"<td>{values[key][2]}</td>" for _, key, _ in columns) + "</tr>"
        classes = "ephemeris" + (f" {extra_class}" if extra_class else "")
        return f'<table class="{classes}"><thead><tr>' + headers + "</tr></thead><tbody>" + rows + "</tbody></table>"

    return (
        "<h3>Weekly Solar-System Ephemeris</h3>"
        + f'<p><strong>Snapshot:</strong> {monday.strftime("%B")} {monday.day}, {monday.year} · 00:00 UTC</p>'
        + notation_toggle("ephemeris")
        + "<p><strong>Naked Eye</strong></p>"
        + table(primary)
        + "<p><strong>Extended targets:</strong></p>"
        + table(extended, extra_class="extended-ephemeris")
        + '<p class="ephemeris-note"><strong>β</strong> = ecliptic latitude (+ north, − south). Observing combines visual magnitude with solar elongation. <span class="text-symbol">☉</span> = Near Sun — not currently observable.</p>'
        + notation_toggle("finder")
        + '<h3>Planet Finder</h3>'
        + planet_finder(monday.year, week)
    )


EPHEMERIS_SECTION = re.compile(
    r'<h3>Weekly Solar-System Ephemeris</h3>.*?'
    r'(?=<h3>(?!Weekly Solar-System Ephemeris</h3>|Planet Finder</h3>)|<h2>|</main>)',
    re.DOTALL,
)
CALENDAR_BLOCK = re.compile(r'(<h3>Calendar</h3>\s*<table\s+class="calendar">.*?</table>)', re.DOTALL)


def put_ephemeris(text, replacement, path):
    new, count = EPHEMERIS_SECTION.subn(lambda _: replacement, text, count=1)
    if count == 1: return new
    new, count = CALENDAR_BLOCK.subn(lambda match: match.group(1) + replacement, text, count=1)
    if count == 1: return new
    raise RuntimeError(f"Could not locate either an ephemeris section or calendar insertion point in {path.relative_to(ROOT)}")


def update_year(year, engine=None):
    generated = computed_ephemeris(year, engine)
    count = week_count(year)
    changed = 0
    for week in range(1, count + 1):
        monday = date.fromisocalendar(year, week, 1)
        values = {
            key: (
                zodiac(generated[key][week - 1][0]),
                beta(generated[key][week - 1][1]),
                visibility_html(generated[key][week - 1][2], generated[key][week - 1][3]),
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
    parser = argparse.ArgumentParser(description="Populate weekly Solar-System ephemeris for one or more ISO years.")
    parser.add_argument("years", nargs="+", type=int, help="ISO week-years to populate")
    args = parser.parse_args()
    years = list(dict.fromkeys(args.years))
    for year in years:
        if not 1900 <= year <= 2100:
            parser.error(f"YEAR must be between 1900 and 2100: {year}")
    return years


def main():
    years = parse_years()
    engine = StarAlmanackEphemeris()
    total = 0
    for year in years:
        changed = update_year(year, engine)
        print(f"Updated {changed} weekly pages for {year}")
        total += changed
    print(f"Updated {total} weekly pages total")


if __name__ == "__main__": main()
