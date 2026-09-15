#!/usr/bin/env python3
"""Populate only the Weekly Solar-System Ephemeris for selected ISO weeks."""
from __future__ import annotations

from datetime import date

import populate_ephemeris as ephemeris
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
    replacement = ephemeris.render_ephemeris(monday, values)

    changed = 0
    path = ephemeris.ROOT / "almanack" / str(year) / f"W{week:02d}" / "index.html"
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
