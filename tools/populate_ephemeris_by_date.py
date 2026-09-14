#!/usr/bin/env python3
"""Populate only the Weekly Solar-System Ephemeris for selected ISO weeks."""
from __future__ import annotations

from datetime import date

import populate_ephemeris as ephemeris
from iso_date_range import group_by_year, parse_range_args

AID_LABELS = {
    "naked_eye": "Naked eye",
    "binoculars": "Binoculars",
    "telescope": "Telescope",
}


def calculate_year(year: int):
    print(f"Calculating {year} ephemeris locally from cached JPL/NAIF source kernels")
    return ephemeris.computed_ephemeris(year)


def observing_html(key, magnitude, elongation) -> str:
    aid = ephemeris.current_visibility(key, magnitude, elongation)
    if not aid:
        return ""
    if aid == "near_sun":
        return ephemeris.VISIBILITY_GLYPHS[aid]

    label = AID_LABELS[aid]
    glyph = ephemeris.VISIBILITY_GLYPHS[aid]
    return (
        '<span class="observing-notation-item" '
        f'data-greek-html="{glyph.replace(chr(34), "&quot;")}" '
        f'data-latin="{label}" '
        f'data-mixed-html="{(glyph + " " + label).replace(chr(34), "&quot;")}">'
        f'{glyph}</span>'
    )


def populate_week(year: int, week: int, generated) -> int:
    monday = date.fromisocalendar(year, week, 1)
    values = {
        key: (
            ephemeris.zodiac(generated[key][week - 1][0]),
            ephemeris.beta(generated[key][week - 1][1]),
            observing_html(key, generated[key][week - 1][2], generated[key][week - 1][3]),
        )
        for _, key, _ in ephemeris.TARGETS
    }
    replacement = ephemeris.render_ephemeris(monday, values)

    changed = 0
    for base in (ephemeris.ROOT / "almanack", ephemeris.ROOT / "Star-Almanack-Repo" / "site"):
        path = base / str(year) / f"W{week:02d}" / "index.html"
        if not path.exists():
            raise RuntimeError(f"Missing weekly page: {path.relative_to(ephemeris.ROOT)}")
        text = path.read_text(encoding="utf-8")
        new = ephemeris.put_ephemeris(text, replacement, path)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1

    print(f"Generated Ephemeris for ISO {year}-W{week:02d}")
    return changed


def main() -> None:
    start, end, weeks = parse_range_args(
        "Populate Star Almanack Ephemeris by inclusive ISO date range"
    )
    total = 0
    for year, selected in group_by_year(weeks).items():
        generated = calculate_year(year)
        for week in selected:
            total += populate_week(year, week, generated)
    print(
        f"Ephemeris complete for {start.isoformat()} through {end.isoformat()}: "
        f"{total} page copies updated"
    )


if __name__ == "__main__":
    main()
