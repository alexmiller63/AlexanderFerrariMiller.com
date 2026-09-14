#!/usr/bin/env python3
"""Populate Sky Notes with descriptor-first JSON records and direct links."""
from __future__ import annotations

from iso_date_range import group_by_year, parse_range_args
from star_almanack_planets import load_weekly_longitudes
import populate_sky_notes_by_date as base
from sky_note_descriptors import build_descriptors, decorate_note_html, write_descriptor_records


def generated_note(year: int, week: int, page_path, yearly, stars: list[dict]) -> dict:
    payload = base.generated_note(year, week, page_path, yearly, stars)
    payload["descriptors"] = build_descriptors(
        payload["fixed_sky"],
        payload["planet_relations"],
        stars,
        base.CONSTELLATION_NAMES,
        base.ASTERISMS,
    )
    payload["descriptor_policy"] = {
        "source_of_truth": "machine-readable JSON",
        "inline_human_descriptors_target": "3-4",
        "additional_json_links_target": "5-6",
        "link_target": "../../descriptors/<id>.json",
        "artwork_descriptor_is_separate": True,
    }
    return payload


def patch_page(path, payload: dict) -> bool:
    text = path.read_text(encoding="utf-8")
    body_start, end = base.sky_note_bounds(text, path)
    rendered = base.render_note(payload["note"])
    rendered = decorate_note_html(rendered, payload["descriptors"])
    placeholder = base.render_artwork_placeholder(payload["artwork"])
    new_body = "\n" + rendered + "\n"
    if placeholder:
        new_body += placeholder + "\n"
    new = text[:body_start] + new_body + text[end:]
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main() -> None:
    start, end, weeks = parse_range_args("Create descriptor-first Star Almanack Sky Notes by inclusive ISO date range")
    stars = base.load_bright_stars()
    grouped = group_by_year(weeks)
    yearly = {year: load_weekly_longitudes(year) for year in grouped}
    changed = 0

    for item in weeks:
        week_key = f"W{item.week:02d}"
        public_page = base.ROOT / "almanack" / str(item.year) / week_key / "index.html"
        if not public_page.exists():
            raise RuntimeError(f"Missing weekly page: {public_page.relative_to(base.ROOT)}")

        payload = generated_note(item.year, item.week, public_page, yearly[item.year], stars)
        write_descriptor_records(payload["descriptors"])
        source = base.write_generated_source(item.year, item.week, payload)

        for root in base.PAGE_ROOTS:
            path = root / str(item.year) / week_key / "index.html"
            if not path.exists():
                raise RuntimeError(f"Missing weekly page: {path.relative_to(base.ROOT)}")
            if patch_page(path, payload):
                changed += 1

        art_state = "artwork descriptor emitted" if payload["artwork"] else "no stellar artwork descriptor needed"
        print(
            f"Generated descriptor-first Sky Note for ISO {item.year}-{week_key}: "
            f"{source.relative_to(base.ROOT)} ({len(payload['descriptors'])} descriptors; {art_state})"
        )

    print(
        f"Descriptor-first Sky Notes complete for {start.isoformat()} through {end.isoformat()}: "
        f"{len(weeks)} notes generated, {changed} page copies updated"
    )


if __name__ == "__main__":
    main()
