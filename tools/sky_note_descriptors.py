#!/usr/bin/env python3
"""Star Almanack Sky Note descriptors with separate machine and human representations.

The preserved descriptor implementation remains the source of descriptor content.
This module adds reader-facing routing: descriptor JSON stays machine-readable data,
while a fixed-sky descriptor links to its canonical story when exactly one curated
story exists for that permanent fixed-object ID.
"""
from __future__ import annotations

import html
from pathlib import Path

import sky_note_descriptors_legacy as _legacy

ROOT = Path(__file__).resolve().parents[1]
STORY_ROOT = ROOT / "stories"

# Preserve the complete descriptor API. Functions below deliberately override the
# two places where reader-facing identity/routing is added.
for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_legacy, _name)


def _canonical_story_url(fixed_object_id: int | None) -> str | None:
    """Return one unambiguous curated human story URL for a permanent object ID."""
    if not fixed_object_id or not STORY_ROOT.exists():
        return None
    matches = sorted(
        path for path in STORY_ROOT.glob(f"*/{fixed_object_id}.md")
        if path.parent.name != "baseline"
    )
    if len(matches) != 1:
        return None
    collection = matches[0].parent.name
    return f"/stories/{collection}/{fixed_object_id}.html"


def _fixed_identity(item: dict) -> tuple[int | None, str]:
    fixed_object_id = item.get("fixed_object_id")
    try:
        fixed_object_id = int(fixed_object_id) if fixed_object_id is not None else None
    except (TypeError, ValueError):
        fixed_object_id = None
    name = str(item.get("name", "")).split(",", 1)[0].strip().casefold()
    return fixed_object_id, name


def build_descriptors(
    fixed: list[dict],
    relations: list[dict],
    stars: list[dict],
    constellation_names: dict[str, str],
    asterisms: dict[str, dict],
) -> list[dict]:
    """Build descriptors and attach permanent identity plus human story routing."""
    records = _legacy.build_descriptors(
        fixed, relations, stars, constellation_names, asterisms
    )
    fixed_by_name = {}
    for item in fixed:
        fixed_object_id, name = _fixed_identity(item)
        if name and fixed_object_id:
            fixed_by_name.setdefault(name, fixed_object_id)

    for record in records:
        fixed_object_id = fixed_by_name.get(str(record.get("name", "")).casefold())
        if not fixed_object_id:
            continue
        record["fixed_object_id"] = fixed_object_id
        human_url = _canonical_story_url(fixed_object_id)
        if human_url:
            record.setdefault("representation", {})["human"] = human_url
            record["representation"]["human_source"] = "curated-story"
    return records


def _linked_name(record: dict) -> str:
    """Render a human link when one exists; never navigate readers to JSON."""
    name = html.escape(str(record["name"]), quote=False)
    representation = record.get("representation") or {}
    human_url = representation.get("human")
    machine_url = representation.get("machine") or _legacy.descriptor_self_reference(record["id"])
    machine_attr = html.escape(str(machine_url), quote=True)
    if human_url:
        href = html.escape(str(human_url), quote=True)
        return (
            f'<a class="descriptor-link" href="{href}" '
            f'data-descriptor-json="{machine_attr}">{name}</a>'
        )
    return f'<span class="descriptor-term" data-descriptor-json="{machine_attr}">{name}</span>'


# The preserved renderer resolves _linked_name through its module globals. Point it
# at the human-aware implementation so all generated prose follows the same rule.
_legacy._linked_name = _linked_name
human_sentence = _legacy.human_sentence
decorate_note_html = _legacy.decorate_note_html
write_descriptor_records = _legacy.write_descriptor_records
descriptor_href = _legacy.descriptor_href
descriptor_self_reference = _legacy.descriptor_self_reference
slugify = _legacy.slugify
