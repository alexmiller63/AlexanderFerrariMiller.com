#!/usr/bin/env python3
"""Populate descriptor-first Sky Notes and story presentations from Calendar IDs."""
from __future__ import annotations

import html
import re

from almanack_sections import replace_section_inner
from iso_date_range import group_by_year, parse_range_args
from star_almanack_planets import load_weekly_longitudes
import populate_sky_notes_by_date as base
from fixed_object_stories import available_stories
from sky_note_descriptors import build_descriptors, decorate_note_html, write_descriptor_records

# Editorial guidance, deliberately separate from candidate discovery. These are
# presentation targets, not limits on the underlying weekly story pool. Raising
# them is useful for debugging and prepares the data model for a later
# Highlights/Wordy presentation toggle.
INLINE_STORY_GUIDANCE = 4
LINKED_STORY_GUIDANCE = 6


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


def story_candidates(fixed_ids: list[int]) -> list[dict]:
    """Return the complete ordered story pool; never apply presentation limits here."""
    candidates = []
    seen = set()
    for fixed_id in fixed_ids:
        for story in available_stories(fixed_id):
            key = (story.collection, story.fixed_object_id)
            if key in seen:
                continue
            seen.add(key)
            candidates.append({
                "fixed_object_id": story.fixed_object_id,
                "collection": story.collection,
                "hed": story.hed,
                "dek": story.dek,
                "body": story.body,
                "url": story.public_url,
                "artwork": story.artwork,
            })
    return candidates


def story_presentations(candidates: list[dict]) -> tuple[list[dict], list[dict]]:
    """Apply tunable presentation guidance without changing the candidate pool."""
    inline = candidates[:INLINE_STORY_GUIDANCE]
    linked = candidates[INLINE_STORY_GUIDANCE:INLINE_STORY_GUIDANCE + LINKED_STORY_GUIDANCE]
    return inline, linked


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


def render_inline_stories(stories: list[dict]) -> str:
    blocks = []
    for story in stories:
        hed = html.escape(story["hed"])
        dek = html.escape(story["dek"])
        body = html.escape(story["body"])
        url = html.escape(story["url"], quote=True)
        body_html = "".join(
            f"<p>{html.escape(' '.join(part.splitlines()))}</p>"
            for part in re.split(r"\n\s*\n", story["body"].strip()) if part.strip()
        ) if body else ""
        blocks.append(
            '<article class="sky-note-story sky-note-story-inline" '
            f'data-fixed-object-id="{story["fixed_object_id"]}" data-story-collection="{html.escape(story["collection"], quote=True)}">'
            f'<h4><a href="{url}">{hed}</a></h4>'
            f'<p class="sky-note-story-dek">{dek}</p>'
            f'{body_html}'
            f'<p><a href="{url}">Read the story.</a></p>'
            '</article>'
        )
    return "\n".join(blocks)


def render_linked_stories(stories: list[dict]) -> str:
    if not stories:
        return ""
    items = []
    for story in stories:
        hed = html.escape(story["hed"])
        dek = html.escape(story["dek"])
        url = html.escape(story["url"], quote=True)
        items.append(
            f'<li data-fixed-object-id="{story["fixed_object_id"]}" '
            f'data-story-collection="{html.escape(story["collection"], quote=True)}">'
            f'<a href="{url}">{hed}</a> — {dek}</li>'
        )
    return '<div class="sky-note-more-stories"><h4>More Sky Notes</h4><ul>' + "".join(items) + '</ul></div>'


def generated_note(year: int, week: int, page_path, yearly, stars: list[dict]) -> dict:
    payload = base.generated_note(year, week, page_path, yearly, stars)
    payload["descriptors"] = build_descriptors(
        payload["fixed_sky"], payload["planet_relations"], stars,
        base.CONSTELLATION_NAMES, base.ASTERISMS,
    )
    fixed_ids = calendar_fixed_object_ids(page_path)
    candidates = story_candidates(fixed_ids)
    inline, linked = story_presentations(candidates)
    payload["calendar_fixed_object_ids"] = fixed_ids
    payload["story_candidates"] = candidates
    payload["inline_stories"] = inline
    payload["linked_stories"] = linked
    # Compatibility field while the artwork pipeline is promoted from one
    # weekly finder to story-scoped artwork descriptors.
    payload["stories"] = candidates
    payload["artwork"] = story_artwork_descriptor(
        year, week, payload["fixed_sky"], payload["planet_relations"], candidates
    )
    payload["descriptor_policy"] = {
        "source_of_truth": "machine-readable JSON",
        "candidate_pool": "complete; presentation guidance never limits discovery",
        "inline_story_guidance": INLINE_STORY_GUIDANCE,
        "linked_story_guidance": LINKED_STORY_GUIDANCE,
        "future_presentations": ["Highlights", "Wordy"],
        "link_target": "../../descriptors/<id>.json",
        "artwork_descriptor_is_separate": True,
        "artwork_source": "explicit story front matter only",
        "story_identity_source": "Calendar data-fixed-object-id only",
        "story_source": "stories/<collection>/<fixed_object_id>.md",
        "inline_story_content": "hed + dek + body",
        "linked_story_content": "hed + dek + story link",
        "annual_note_is_separate_from_evergreen_story": True,
    }
    return payload


def patch_page(path, payload: dict) -> bool:
    text = path.read_text(encoding="utf-8")
    rendered = base.render_note(payload["note"])
    rendered = decorate_note_html(rendered, payload["descriptors"])
    inline = render_inline_stories(payload.get("inline_stories", []))
    linked = render_linked_stories(payload.get("linked_stories", []))
    placeholder = base.render_artwork_placeholder(payload["artwork"])
    body = rendered + "\n"
    if inline:
        body += inline + "\n"
    if linked:
        body += linked + "\n"
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
            f"{len(payload['story_candidates'])} story candidates; "
            f"{len(payload['inline_stories'])} inline; {len(payload['linked_stories'])} linked; {art_state})"
        )

    print(
        f"Descriptor-first Sky Notes complete for {start.isoformat()} through {end.isoformat()}: "
        f"{len(weeks)} notes generated, {changed} page copies updated"
    )


if __name__ == "__main__":
    main()
