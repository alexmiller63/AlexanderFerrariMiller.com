#!/usr/bin/env python3
"""Populate Sky Notes with descriptor-first records and evergreen story previews."""
from __future__ import annotations

import html
import json
import re

from iso_date_range import group_by_year, parse_range_args
from star_almanack_planets import load_weekly_longitudes
import populate_sky_notes_by_date as base
from fixed_object_stories import available_stories
from sky_note_descriptors import build_descriptors, decorate_note_html, write_descriptor_records

FIXED_OBJECTS_DB = base.ROOT / "database" / "fixed-objects.json"


def load_story_identity_index() -> tuple[dict[str, int], dict[str, int]]:
    """Build lookup indexes only for resolving calendar text to permanent IDs.

    Story lookup itself is always collection + fixed_object_id. Names and
    catalog labels stop being keys once the permanent identity is resolved.
    """
    data = json.loads(FIXED_OBJECTS_DB.read_text(encoding="utf-8"))
    names: dict[str, int] = {}
    messier: dict[str, int] = {}
    for obj in data["fixed_objects"]:
        fixed_id = int(obj["fixed_object_id"])
        for record in obj.get("source_records", []):
            facts = record.get("facts", {})
            name = facts.get("name")
            if name:
                names.setdefault(str(name).casefold(), fixed_id)
            key = str(record.get("source_key", "")).upper()
            if re.fullmatch(r"M(?:110|10\d|[1-9]\d?)", key):
                messier.setdefault(key, fixed_id)
    return names, messier


def resolve_fixed_object_id(item: dict, names: dict[str, int], messier: dict[str, int]) -> int | None:
    label = str(item.get("name", ""))
    match = re.search(r"(?<![A-Za-z0-9])M(?:110|10\d|[1-9]\d?)(?!\d)", label, flags=re.I)
    if match:
        found = messier.get(match.group(0).upper())
        if found is not None:
            return found
    candidates = [label, label.split(",", 1)[0], re.sub(r"\s*\([^)]*\)\s*", "", label).strip()]
    for candidate in candidates:
        found = names.get(candidate.strip().casefold())
        if found is not None:
            return found
    return None


def story_previews(fixed_sky: list[dict], names: dict[str, int], messier: dict[str, int]) -> list[dict]:
    previews = []
    seen = set()
    for item in fixed_sky:
        fixed_id = resolve_fixed_object_id(item, names, messier)
        if fixed_id is None:
            continue
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
            })
    return previews


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


def generated_note(year: int, week: int, page_path, yearly, stars: list[dict], identity_index=None) -> dict:
    payload = base.generated_note(year, week, page_path, yearly, stars)
    payload["descriptors"] = build_descriptors(
        payload["fixed_sky"], payload["planet_relations"], stars,
        base.CONSTELLATION_NAMES, base.ASTERISMS,
    )
    if identity_index is None:
        identity_index = load_story_identity_index()
    payload["stories"] = story_previews(payload["fixed_sky"], *identity_index)
    payload["descriptor_policy"] = {
        "source_of_truth": "machine-readable JSON",
        "inline_human_descriptors_target": "3-4",
        "additional_json_links_target": "5-6",
        "link_target": "../../descriptors/<id>.json",
        "artwork_descriptor_is_separate": True,
        "story_source": "stories/<collection>/<fixed_object_id>.md",
        "story_preview": "hed + dek",
        "annual_note_is_separate_from_evergreen_story": True,
    }
    return payload


def patch_page(path, payload: dict) -> bool:
    text = path.read_text(encoding="utf-8")
    body_start, end = base.sky_note_bounds(text, path)
    rendered = base.render_note(payload["note"])
    rendered = decorate_note_html(rendered, payload["descriptors"])
    stories = render_story_previews(payload.get("stories", []))
    placeholder = base.render_artwork_placeholder(payload["artwork"])
    new_body = "\n" + rendered + "\n"
    if stories:
        new_body += stories + "\n"
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
    identity_index = load_story_identity_index()
    grouped = group_by_year(weeks)
    yearly = {year: load_weekly_longitudes(year) for year in grouped}
    changed = 0

    for item in weeks:
        week_key = f"W{item.week:02d}"
        public_page = base.ROOT / "almanack" / str(item.year) / week_key / "index.html"
        if not public_page.exists():
            raise RuntimeError(f"Missing weekly page: {public_page.relative_to(base.ROOT)}")

        payload = generated_note(item.year, item.week, public_page, yearly[item.year], stars, identity_index)
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
            f"{source.relative_to(base.ROOT)} ({len(payload['descriptors'])} descriptors; "
            f"{len(payload['stories'])} story previews; {art_state})"
        )

    print(
        f"Descriptor-first Sky Notes complete for {start.isoformat()} through {end.isoformat()}: "
        f"{len(weeks)} notes generated, {changed} page copies updated"
    )


if __name__ == "__main__":
    main()
