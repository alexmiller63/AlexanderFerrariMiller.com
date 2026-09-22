#!/usr/bin/env python3
"""Populate Ephemeris + Planet Finder only for ISO weeks in a date range."""
from __future__ import annotations

from datetime import date
import generate_planet_finders as finder
import populate_ephemeris as ephemeris
from almanack_sections import replace_section_inner
from almanack_paths import week_dir, week_index
from iso_date_range import group_by_year, parse_range_args
from planet_finder_layout import patch_file as patch_planet_finder_layout
from star_almanack_ephemeris import StarAlmanackEphemeris

FINDER_FILENAMES = {
    "greek": "planet-finder-greek-symbols.svg",
    "latin": "planet-finder-latin.svg",
    "mixed": "planet-finder-mixed-learner.svg",
}


def calculate_year(year: int, engine: StarAlmanackEphemeris):
    print(f"Calculating {year} weekly planetary snapshots from cached JPL source kernels")
    return ephemeris.computed_ephemeris(year, engine)


def finder_bodies(generated, week: int):
    result = []
    for name in finder.CANONICAL:
        key = finder.BODY_NAMES[name]
        longitude = generated[key][week - 1][0] % 360.0
        result.append((finder.BODY_SYMBOLS[key], name, longitude))
    return result


def split_rendered_sections(rendered: str) -> tuple[str, str]:
    finder_marker = ephemeris.notation_toggle("finder") + "<h3>Planet Finder</h3>"
    if finder_marker not in rendered:
        raise RuntimeError("Rendered Ephemeris is missing its Planet Finder boundary")
    ephemeris_html, finder_body = rendered.split(finder_marker, 1)
    return ephemeris_html, finder_marker + finder_body


def populate_week(
    year: int,
    week: int,
    generated,
    budget: dict,
    week_number: int,
    total_weeks: int,
) -> int:
    monday = date.fromisocalendar(year, week, 1)
    context_label = f"week={week_number}/{total_weeks} ISO={year}-W{week:02d}"
    print(
        f"Starting ISO {year}-W{week:02d} (Monday {monday.isoformat()}) "
        f"per-body-attempt-cap={budget['max_node_candidates']:,}",
        flush=True,
    )
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
    ephemeris_html, finder_html = split_rendered_sections(rendered)

    changed = 0
    ephemeris_path = week_index(year, week)
    finder_path = week_index(year, week)
    for path, section, body in (
        (ephemeris_path, 3, ephemeris_html),
        (finder_path, 4, finder_html),
    ):
        if not path.exists():
            raise RuntimeError(f"Missing typed weekly page: {path.relative_to(ephemeris.ROOT)}")
        text = path.read_text(encoding="utf-8")
        new = replace_section_inner(text, section, body, path)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1
    patch_planet_finder_layout(finder_path)

    bodies = finder_bodies(generated, week)
    # The week is the publication unit. Keep finder assets beneath the week
    # in both canonical and published trees so each weekly page is a complete,
    # self-contained package and its relative finders/... links are valid.
    outdirs = (
        week_dir(year, week) / "finders",
        ephemeris.ROOT / "site" / str(year) / f"W{week:02d}" / "planet-finder" / "finders",
    )
    for outdir in outdirs:
        outdir.mkdir(parents=True, exist_ok=True)

    for mode, filename in FINDER_FILENAMES.items():
        # Each independently searched layout gets its own complete safety
        # envelope. The per-body candidate cap and the wall-clock ceiling
        # therefore apply independently to Greek, Latin, and Mixed.
        mode_budget = finder.new_search_budget()
        svg = finder.render(
            year, week, monday, mode, bodies,
            budget=mode_budget,
            context_label=context_label,
        )
        for outdir in outdirs:
            (outdir / filename).write_text(svg, encoding="utf-8")

    for outdir in outdirs:
        missing = [filename for filename in FINDER_FILENAMES.values() if not (outdir / filename).is_file()]
        if missing:
            raise RuntimeError(
                f"Planet Finder publication incomplete in {outdir.relative_to(ephemeris.ROOT)}: "
                + ", ".join(missing)
            )

    print(f"Generated Ephemeris + Planet Finder for ISO {year}-W{week:02d}", flush=True)
    return changed


def main() -> None:
    start, end, weeks = parse_range_args("Populate Star Almanack Ephemeris + Planet Finder by inclusive ISO date range")
    grouped = group_by_year(weeks)
    engine = StarAlmanackEphemeris()
    total = 0
    total_weeks = len(weeks)
    week_number = 0
    budget = finder.new_search_budget()
    print(
        f"Planet Finder SEARCH LIMITS: {budget['max_node_candidates']:,} attempts per body; "
        f"{budget['max_seconds']:.1f}s independently for each mode",
        flush=True,
    )
    for year, selected in grouped.items():
        generated = calculate_year(year, engine)
        for week in selected:
            week_number += 1
            total += populate_week(
                year, week, generated, budget, week_number, total_weeks
            )
    print(
        f"Planet Finder RUN COMPLETE: per-body-attempt-cap={budget['max_node_candidates']:,} "
        f"per mode across {total_weeks} weeks",
        flush=True,
    )
    print(f"Ephemeris + Planet Finder complete for {start.isoformat()} through {end.isoformat()}: {total} page copies updated")


if __name__ == "__main__":
    main()
