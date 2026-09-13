#!/usr/bin/env python3
"""Populate Ephemeris + Planet Finder only for ISO weeks in a date range."""
from __future__ import annotations

from datetime import date

import generate_planet_finders as finder
import populate_ephemeris as ephemeris
from iso_date_range import group_by_year, parse_range_args

FINDER_FILENAMES = {
    "greek": "planet-finder-greek-symbols.svg",
    "latin": "planet-finder-latin.svg",
    "mixed": "planet-finder-mixed-learner.svg",
}


def fetch_year(year: int) -> dict[str, list[tuple[float, float, float | None, float | None]]]:
    generated = {}
    for _, key, command in ephemeris.TARGETS:
        print(f"Fetching {year} {key} from JPL Horizons")
        generated[key] = ephemeris.horizons_ephemeris(year, command)
    return generated


def finder_bodies(generated, week: int):
    result = []
    for name in finder.CANONICAL:
        key = finder.BODY_NAMES[name]
        longitude = generated[key][week - 1][0] % 360.0
        result.append((finder.BODY_SYMBOLS[key], name, longitude))
    return result


def populate_week(year: int, week: int, generated) -> int:
    monday = date.fromisocalendar(year, week, 1)
    values = {
        key: (
            ephemeris.zodiac(generated[key][week - 1][0]),
            ephemeris.beta(generated[key][week - 1][1]),
            ephemeris.visibility_html(generated[key][week - 1][2], generated[key][week - 1][3]),
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

    bodies = finder_bodies(generated, week)
    outdir = ephemeris.ROOT / "almanack" / str(year) / f"W{week:02d}" / "finders"
    outdir.mkdir(parents=True, exist_ok=True)
    for mode, filename in FINDER_FILENAMES.items():
        svg = finder.render(year, week, monday, mode, bodies)
        (outdir / filename).write_text(svg, encoding="utf-8")

    print(f"Generated Ephemeris + Planet Finder for ISO {year}-W{week:02d}")
    return changed


def main() -> None:
    start, end, weeks = parse_range_args("Populate Star Almanack Ephemeris + Planet Finder by inclusive ISO date range")
    grouped = group_by_year(weeks)
    total = 0
    for year, selected in grouped.items():
        generated = fetch_year(year)
        for week in selected:
            total += populate_week(year, week, generated)
    print(f"Ephemeris + Planet Finder complete for {start.isoformat()} through {end.isoformat()}: {total} page copies updated")


if __name__ == "__main__":
    main()
