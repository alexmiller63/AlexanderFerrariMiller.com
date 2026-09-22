#!/usr/bin/env python3
"""Populate only the Weekly Solar-System Ephemeris for selected ISO weeks."""
from __future__ import annotations

from datetime import date

import populate_ephemeris as ephemeris
from almanack_sections import replace_section_inner
from almanack_paths import typed_page
from iso_date_range import group_by_year, parse_range_args


def calculate_year(year: int):
    print(f"Calculating {year} ephemeris locally from cached JPL/NAIF source kernels")
    return ephemeris.computed_ephemeris(year)


def populate_week(year: int, week: int, generated) -> int:
    monday = date.fromisocalendar(year, week, 1)
    values = {}
    for _, key, _ in ephemeris.TARGETS:
        sample = generated[key][week - 1]
        aid = ephemeris.current_visibility(key, sample[2], sample[3], sample[6])
        values[key] = {
            "position": ephemeris.zodiac(sample[0]),
            "beta": ephemeris.beta(sample[1]),
            "observing": ephemeris.observing_html(key, sample[2], sample[3], sample[6]),
            "normal_label": ephemeris.observing_label(key, sample[2], sample[3], False),
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
    rendered = ephemeris.render_ephemeris(monday, values)
    finder_marker = ephemeris.notation_toggle("finder") + "<h3>Planet Finder</h3>"
    ephemeris_html = rendered.split(finder_marker, 1)[0]

    changed = 0
    path = typed_page(year, week, "ephemeris")
    if not path.exists():
        raise RuntimeError(f"Missing weekly page: {path.relative_to(ephemeris.ROOT)}")
    text = path.read_text(encoding="utf-8")
    new = replace_section_inner(text, 3, ephemeris_html, path)
    runtime = '<script src="../../js/ephemeris.js"></script>'
    if runtime not in new:
        if '</body>' not in new:
            raise RuntimeError(f"Missing </body> in weekly page: {path.relative_to(ephemeris.ROOT)}")
        new = new.replace('</body>', runtime + '\n</body>', 1)
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
