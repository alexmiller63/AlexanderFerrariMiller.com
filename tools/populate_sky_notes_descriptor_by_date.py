#!/usr/bin/env python3
"""Populate descriptor-first Sky Notes and story previews from Calendar IDs."""
from __future__ import annotations

import html
import json
import re

from almanack_sections import replace_section_inner
from iso_date_range import group_by_year, parse_range_args
from star_almanack_planets import load_weekly_longitudes
import populate_sky_notes_by_date as base
from fixed_object_stories import available_stories
from sky_note_descriptors import build_descriptors, decorate_note_html, write_descriptor_records


def calendar_fixed_object_ids(page_path) -> list[int]:
    """Read permanent object identities carried by Calendar event cells."""
    text = page_path.read_text(encoding="utf-8")
    ids = []
    seen = set()
    for raw in re.findall(r'\bdata-fixed-object-id="(\d+)"', text):
        fixed_id = int(raw)
        if fixed_id not in seen:
            seen.add(fixed_id)
            ids.append(fixed_id)
    return ids


def story_previews(fixed_ids: list[int]) -> list[dict]:
    previews = []
    seen = set()
    for fixed_id in fixed_ids:
        for story in available_stories(fixed_id):
            key = (story.collection, story.fixed_object_id)
            if key in seen:
                continue
            seen.add(key)
            previews.append({
                "fixed_object_id": story.fixed_object_id,
                "collection": story.collection,
                "hed": story.hed,
                "dek": story.dek,
                "url": story.public_url,
                "artwork": story.artwork,
            })
    return previews


def story_artwork_descriptor(year: int, week: int, fixed_sky: list[dict], relations: list[dict], stories: list[dict]) -> dict | None:
    requests = [story for story in stories if story.get("artwork")]
    if not requests:
        return None
    kinds = {story["artwork"] for story in requests}
    if kinds != {"stellar-finder"}:
        raise RuntimeError(f"Unsupported story artwork request(s) for ISO {year}-W{week:02d}: {sorted(kinds)}")
    descriptor = base.artwork_descriptor(year, week, fixed_sky, relations)
    if descriptor is None:
        raise RuntimeError(
            f"ISO {year}-W{week:02d}: Calendar story requests stellar-finder artwork "
            "but accepted fixed-sky geometry cannot supply it"
        )
    descriptor["story_sources"] = [
        {"collection": story["collection"], "fixed_object_id": story["fixed_object_id"], "artwork": story["artwork"]}
        for story in requests
    ]
    return descriptor


def render_story_previews(previews: list[dict]) -> str:
    if not previews:
        return ""
    blocks = []
    for story in previews:
        hed = html.escape(story["hed"])
        dek = html.escape(story["dek"])
        url = html.escape(story["url"], quote=True)
        blocks.append(
            '<article class="sky-note-story-preview" '
            f'data-fixed-object-id="{story["fixed_object_id"]}" data-story-collection="{html.escape(story["collection"], quote=True)}">'
            f'<h4><a href="{url}">{hed}</a></h4>'
            f'<p>{dek} <a href="{url}">Read the story.</a></p>'
            '</article>'
        )
    return "\n".join(blocks)


def generated_note(year: int, week: int, page_path, yearly, stars: list[dict]) -> dict:
    payload = base.generated_note(year, week, page_path, yearly, stars)
    payload["descriptors"] = build_descriptors(
        payload["fixed_sky"], payload["planet_relations"], stars,
        base.CONSTELLATION_NAMES, base.ASTERISMS,
    )
    fixed_ids = calendar_fixed_object_ids(page_path)
    payload["calendar_fixed_object_ids"] = fixed_ids
    payload["stories"] = story_previews(fixed_ids)
    payload["artwork"] = story_artwork_descriptor(
        year, week, payload["fixed_sky"], payload["planet_relations"], payload["stories"]
    )
    payload["descriptor_policy"] = {
        "source_of_truth": "machine-readable JSON",
        "inline_human_descriptors_target": "3-4",
        "additional_json_links_target": "5-6",
        "link_target": "../../descriptors/<id>.json",
        "artwork_descriptor_is_separate": True,
        "artwork_source": "explicit story front matter only",
        "story_identity_source": "Calendar data-fixed-object-id only",
        "story_source": "stories/<collection>/<fixed_object_id>.md",
        "story_preview": "hed + dek",
        "annual_note_is_separate_from_evergreen_story": True,
    }
    return payload


def patch_page(path, payload: dict) -> bool:
    text = path.read_text(encoding="utf-8")
    rendered = base.render_note(payload["note"])
    rendered = decorate_note_html(rendered, payload["descriptors"])
    stories = render_story_previews(payload.get("stories", []))
    placeholder = base.render_artwork_placeholder(payload["artwork"])
    body = rendered + "\n"
    if stories:
        body += stories + "\n"
    if placeholder:
        body += placeholder + "\n"
    section_html = '<h3>Sky Notes</h3><div class="sky-note">\n' + body + '</div>'
    new = replace_section_inner(text, 5, section_html, path)
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

        art_state = "story-declared artwork descriptor emitted" if payload["artwork"] else "no story-declared artwork"
        print(
            f"Generated descriptor-first Sky Note for ISO {item.year}-{week_key}: "
            f"{source.relative_to(base.ROOT)} ({len(payload['descriptors'])} descriptors; "
            f"{len(payload['stories'])} story previews; {art_state})"
        )

    print(
        f"Descriptor-first Sky Notes complete for {start.isoformat()} through {end.isoformat()}: "
        f"{len(weeks)} notes generated, {changed} page copies updated"
    )


if __name__ == "__main__":
    main()
