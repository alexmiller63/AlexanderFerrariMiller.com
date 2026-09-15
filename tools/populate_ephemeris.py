#!/usr/bin/env python3
"""Populate weekly Star Almanack Solar-System ephemerides from local source kernels.

The weekly table is a civil-time presentation snapshot: each row is sampled at
Monday 00:00 UTC, then calculated locally from cached JPL/NAIF SPK source data.
No Horizons or other answer service is queried.
"""
from __future__ import annotations

import argparse
import csv
import html
import re
from datetime import date
from pathlib import Path

from star_almanack_ephemeris import StarAlmanackEphemeris

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LATITUDE_DEG = 45.0
SIGNS = "♈♉♊♋♌♍♎♏♐♑♒♓"

TARGETS = [
    ("☉ Sun", "sun", "sun"), ("☽ Moon", "moon", "moon"), ("☿ Mercury", "mercury", "mercury"),
    ("♀ Venus", "venus", "venus"), ("♂ Mars", "mars", "mars"), ("♃ Jupiter", "jupiter", "jupiter"),
    ("♄ Saturn", "saturn", "saturn"), ("⚳ Ceres", "ceres", "ceres"), ("♅ Uranus", "uranus", "uranus"),
    ("♆ Neptune", "neptune", "neptune"), ("♇ Pluto", "pluto", "pluto"),
]

VISIBILITY_GLYPH_ROOT = "../../../assets/almanack/visibility-glyphs/masters/"
_TELESCOPE_GLYPH = f'<img class="visibility-glyph" src="{VISIBILITY_GLYPH_ROOT}telescope.svg" alt="Telescope" aria-label="Telescope">'
VISIBILITY_GLYPHS = {
    "naked_eye": f'<img class="visibility-glyph" src="{VISIBILITY_GLYPH_ROOT}eye.svg" alt="Naked eye" aria-label="Naked eye">',
    "binoculars": f'<img class="visibility-glyph" src="{VISIBILITY_GLYPH_ROOT}binoculars.svg" alt="Binoculars" aria-label="Binoculars">',
    "telescope": _TELESCOPE_GLYPH,
    "substantial_telescope": (
        '<span class="substantial-telescope" role="img" aria-label="Substantial telescope">'
        + _TELESCOPE_GLYPH + _TELESCOPE_GLYPH + '</span>'
    ),
    "daylight": '<span class="text-symbol" role="img" aria-label="Daylight" title="Daylight">☉︎</span>',
    "solar_glare": '<span class="text-symbol" role="img" aria-label="Solar glare" title="Solar glare">☉︎</span>',
    "visible": '<span class="text-symbol" role="img" aria-label="visible" title="visible">☉︎</span>',
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
            rise, setting = engine.rise_set_lat(sample, key, DEFAULT_LATITUDE_DEG)
            daylight = engine.daylight_at_observing_time(sample, DEFAULT_LATITUDE_DEG)
            generated[key].append((
                sample.longitude_deg,
                sample.latitude_deg,
                sample.magnitude,
                sample.elongation_deg,
                rise,
                setting,
                daylight,
                sample.right_ascension_hours,
                sample.declination_deg,
                sample.sun_right_ascension_hours,
                sample.sun_declination_deg,
            ))
    return generated


def zodiac_text(longitude):
    """Render a machine-readable zodiac longitude without presentation markup."""
    minutes = int(round((longitude % 360) * 60)) % (360 * 60)
    sign, within = divmod(minutes, 1800)
    degree, minute = divmod(within, 60)
    return f"{SIGNS[sign]} {degree}°{minute:02d}′"


def zodiac(longitude):
    position = zodiac_text(longitude)
    glyph, value = position.split(" ", 1)
    return f"{symbol_html(glyph)} {value}"


def beta(latitude):
    sign = "+" if latitude >= 0 else "−"
    minutes = int(round(abs(latitude) * 60))
    degree, minute = divmod(minutes, 60)
    return f"β {sign}{degree}°{minute:02d}′"


def current_visibility(key, magnitude, elongation, daylight=False):
    if key == "sun":
        return "visible"
    if elongation is not None and elongation < 20.0:
        return "solar_glare"
    if magnitude is not None and elongation is not None:
        if magnitude <= 3.5:
            return "daylight" if daylight else "naked_eye"
        if magnitude <= 7.5: return "binoculars"
        if magnitude <= 12.0: return "telescope"
        return "substantial_telescope"

    if key == "moon": return "daylight" if daylight else "naked_eye"
    if key == "ceres": return "telescope"
    if key == "pluto": return "substantial_telescope"
    return None


def visibility_html(key, magnitude, elongation, daylight=False):
    aid = current_visibility(key, magnitude, elongation, daylight)
    return VISIBILITY_GLYPHS[aid] if aid else ""


def observing_label(key, magnitude, elongation, daylight=False):
    labels = {
        "naked_eye": "Naked eye",
        "binoculars": "Binoculars",
        "telescope": "Telescope",
        "substantial_telescope": "Substantial telescope",
        "daylight": "Daylight",
        "solar_glare": "Solar glare",
        "visible": "visible",
    }
    aid = current_visibility(key, magnitude, elongation, daylight)
    return labels.get(aid, "")


def observing_html(key, magnitude, elongation, daylight=False):
    aid = current_visibility(key, magnitude, elongation, daylight)
    if not aid:
        return ""
    glyph = VISIBILITY_GLYPHS[aid]
    label = observing_label(key, magnitude, elongation, daylight)
    return (
        '<span class="observing-notation-item" '
        f'data-greek-html="{html.escape(glyph, quote=True)}" '
        f'data-latin="{html.escape(label, quote=True)}" '
        f'data-mixed-html="{html.escape(glyph + " " + label, quote=True)}">'
        f'{glyph}</span>'
    )


def render_observing_status(key, sample_values):
    aid = current_visibility(
        key,
        sample_values["magnitude"],
        sample_values["elongation"],
        sample_values["daylight"],
    )
    return {
        "aid": aid,
        "label": observing_label(
            key,
            sample_values["magnitude"],
            sample_values["elongation"],
            sample_values["daylight"],
        ),
        "html": observing_html(
            key,
            sample_values["magnitude"],
            sample_values["elongation"],
            sample_values["daylight"],
        ),
    }

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

    def table(columns, extra_class=""):
        headers = '<th scope="col">Measure</th>' + "".join(
            f"<th scope=\"col\">{target_heading(display)}</th>" for display, _, _ in columns
        )
        rows = []
        for label, field in (("Body", "position"), ("Observing", "observing"), ("Rise", "rise"), ("Set", "set")):
            cells = []
            for _, key, _ in columns:
                item = values[key]
                if field == "position":
                    content = f'{item["position"]}<br><small>{item["beta"]}</small>'
                elif field == "observing":
                    content = item["observing"]
                else:
                    content = item[field]
                if field in ("rise", "set"):
                    content = (
                        f'<td class="ephemeris-{field.lower()}" '
                        f'data-ra-hours="{item["ra_hours"]:.9f}" '
                        f'data-dec-deg="{item["dec_deg"]:.9f}" '
                        f'data-sun-ra-hours="{item["sun_ra_hours"]:.9f}" '
                        f'data-horizon-deg="{item["horizon_deg"]:.4f}">{content}</td>'
                    )
                elif field == "observing":
                    content = (
                        f'<td class="ephemeris-observing" '
                        f'data-normal-label="{html.escape(item["normal_label"], quote=True)}" '
                        f'data-solar-glare="{str(item["solar_glare"]).lower()}" '
                        f'data-sun-special="{str(item["sun_special"]).lower()}" '
                        f'data-sun-dec-deg="{item["sun_dec_deg"]:.9f}">'
                        f'{content}</td>'
                    )
                else:
                    content = f"<td>{content}</td>"
                cells.append(content)
            rows.append(f'<tr><th scope="row">{label}</th>{"".join(cells)}</tr>')
        classes = "ephemeris" + (f" {extra_class}" if extra_class else "")
        return f'<table class="{classes}"><thead><tr>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table>'

    return (
        "<h3>Weekly Solar-System Ephemeris</h3>"
        + f'<p><strong>Snapshot:</strong> {monday.strftime("%B")} {monday.day}, {monday.year} · 00:00 UTC</p>'
        + '<p class="ephemeris-latitude-control"><label for="ephemeris-latitude"><strong>Observer latitude:</strong> <input id="ephemeris-latitude" name="ephemeris-latitude" type="number" min="-90" max="90" step="0.1" value="45" data-ephemeris-latitude>°</label> <span>(default +45°)</span></p>'
        + notation_toggle("ephemeris")
        + table(primary)
        + "<p><strong>Extended targets:</strong></p>"
        + table(extended, "extended-ephemeris")
        + '<p class="ephemeris-note"><strong>β</strong> = ecliptic latitude (+ north, − south). Rise and set are Local Apparent Time for the selected latitude. Naked-eye classification becomes <strong>Daylight</strong> when the Sun is above the horizon at 21:00 LAT, and <strong>Solar glare</strong> when the Sun is below the horizon but the body is too close to the Sun. The Sun uses glyph <span class="text-symbol">☉</span> and text <strong>visible</strong>.</p>'
        + notation_toggle("finder")
        + "<h3>Planet Finder</h3>"
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


def write_preserved_weekly_table(year, generated):
    """Persist the shared calculation layer consumed by presentation generators."""
    path = ROOT / "Star-Almanack-Repo" / f"weekly-ephemeris-{year}.csv"
    fields = ["iso_week", "monday_utc", *[key for _, key, _ in TARGETS if key != "pluto"]]
    rows = []
    for week in range(1, week_count(year) + 1):
        monday = date.fromisocalendar(year, week, 1)
        row = {"iso_week": f"{year}-W{week:02d}", "monday_utc": monday.isoformat()}
        for key in fields[2:]:
            row[key] = zodiac_text(generated[key][week - 1][0])
        rows.append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def update_year(year, engine=None):
    generated = computed_ephemeris(year, engine)
    write_preserved_weekly_table(year, generated)
    count = week_count(year)
    changed = 0
    for week in range(1, count + 1):
        monday = date.fromisocalendar(year, week, 1)
        values = {}
        for _, key, _ in TARGETS:
            sample = generated[key][week - 1]
            aid = current_visibility(key, sample[2], sample[3], sample[6])
            values[key] = {
                "position": zodiac(sample[0]),
                "beta": beta(sample[1]),
                "observing": observing_html(key, sample[2], sample[3], sample[6]),
                "normal_label": observing_label(key, sample[2], sample[3], False),
                "solar_glare": aid == "solar_glare",
                "sun_special": key == "sun",
                "rise": sample[4],
                "set": sample[5],
                "ra_hours": sample[7],
                "dec_deg": sample[8],
                "sun_ra_hours": sample[9],
                "sun_dec_deg": sample[10],
                "horizon_deg": -0.8333 if key == "sun" else -0.5667,
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
