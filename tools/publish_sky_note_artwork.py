#!/usr/bin/env python3
"""Publish time-varying planet finders into generated weekly pages."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from iso_date_range import parse_range_args
from almanack_paths import week_index

ROOT = Path(__file__).resolve().parents[1]
ARTWORK_ROOT = ROOT / "sky-notes-artwork" / "weeks"
DESCRIPTOR_ROOT = ROOT / "generated-sky-notes"

PLACEHOLDER_RE = re.compile(r'<figure class="sky-note-artwork-placeholder"\s+data-sky-note-artwork-placeholder="true"\s+data-artwork-descriptor="[^"]*">.*?</figure>', flags=re.S)
PUBLISHED_RE = re.compile(r'<figure class="sky-note-artwork"[^>]*>.*?</figure>', flags=re.S)
RELATED_RE = re.compile(r'<div class="related-descriptor-artwork"\s+data-related-descriptor-artwork="true">.*?</div>', flags=re.S)
PATHFINDER_LINK_RE = re.compile(r'<a class="planet-pathfinder-link"[^>]*>.*?</a>', flags=re.S)


def publish_page(path: Path, payload: dict, year: int, week: int) -> bool:
    text = path.read_text(encoding="utf-8")
    new = PUBLISHED_RE.sub("", text)
    new = RELATED_RE.sub("", new)
    new = PLACEHOLDER_RE.sub("", new)\n    new = PATHFINDER_LINK_RE.sub("", new)

    descriptors = payload.get("planet_finder_artworks")
    if descriptors is None:
        legacy = payload.get("planet_finder_artwork")
        descriptors = [legacy] if legacy else []
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            continue
        route = descriptor.get("finder_route") or {}
        planet = str(route.get("planet") or "Planet")
        reference = str(route.get("reference_star") or "")
        object_id = descriptor.get("object_id")
        if not isinstance(object_id, int):
            raise RuntimeError(f"{year}-W{week:02d}: planetary finder for {planet} lacks numeric object_id")
        svg = ARTWORK_ROOT / str(year) / f"W{week:02d}" / f"{object_id}.svg"
        if not svg.exists():
            raise RuntimeError(f"Planet finder SVG is missing: {svg.relative_to(ROOT)}")
        rendering_id = str(descriptor.get("id") or f"{year}-W{week:02d}-{object_id}")
        constellation = str(descriptor.get("constellation") or "")
        title = " ".join(part for part in (
            planet,
            f"near {reference}" if reference else "",
            f"in {constellation}" if constellation else "",
        ) if part)
        finder_dir = path.parent / "finders"
        finder_dir.mkdir(parents=True, exist_ok=True)
        finder_path = finder_dir / f"{object_id}.html"
        finder_html = (
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            '</head><body><main>'
            f'<h1>{html.escape(title)}</h1>'
            f'<figure class="sky-note-artwork planet-finder-artwork" data-planet-finder="true" '
            f'data-object-id="{object_id}" data-rendering-id="{html.escape(rendering_id, quote=True)}">'
            f'<img src="../../../../sky-notes-artwork/weeks/{year}/W{week:02d}/{object_id}.svg" '
            f'alt="{html.escape(title)} finder chart">'
            f'<figcaption>{html.escape(title)}</figcaption></figure>'
            f'<p><a href="../">Back to ISO {year}-W{week:02d}</a></p>'
            '</main></body></html>\n'
        )
        if not finder_path.exists() or finder_path.read_text(encoding="utf-8") != finder_html:
            finder_path.write_text(finder_html, encoding="utf-8")
        figure = (
            f'<p class="planet-pathfinder"><a class="planet-pathfinder-link" '
            f'href="finders/{object_id}.html">Find {html.escape(planet)} with the Pathfinder.</a></p>'
        )
        anchor = f'id="sky-note-object-{object_id}"'
        match = re.search(rf'<(?P<tag>section|article|div)\b[^>]*{re.escape(anchor)}[^>]*>', new)
        if not match:
            raise RuntimeError(
                f"{year}-W{week:02d}: missing Sky Notes destination sky-note-object-{object_id} for {planet}"
            )
        insert_at = match.end()
        new = new[:insert_at] + figure + new[insert_at:]

    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True

def main() -> None:
    start, end, weeks = parse_range_args("Publish object-owned Star Almanack Sky Note artwork")
    changed = published = 0
    for item in weeks:
        week_key = f"W{item.week:02d}"
        payload_path = DESCRIPTOR_ROOT / str(item.year) / f"{week_key}.json"
        if not payload_path.exists():
            continue
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        published += 1
        page = week_index(item.year, item.week)
        if not page.exists():
            raise RuntimeError(f"Weekly page is missing: {page.relative_to(ROOT)}")
        if publish_page(page, payload, item.year, item.week):
            changed += 1
    print(f"Published weekly planet finder artwork for {start.isoformat()} through {end.isoformat()}: {published} weeks, {changed} page copies updated")


if __name__ == "__main__":
    main()
