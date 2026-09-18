#!/usr/bin/env python3
"""Publish fixed-object-owned Sky Note finders into generated weekly pages."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from iso_date_range import parse_range_args

ROOT = Path(__file__).resolve().parents[1]
PAGE_ROOTS = (ROOT / "site", ROOT / "almanack")
ARTWORK_ROOT = ROOT / "sky-notes-artwork" / "objects"
DESCRIPTOR_ROOT = ROOT / "generated-sky-notes"

PLACEHOLDER_RE = re.compile(r'<figure class="sky-note-artwork-placeholder"\s+data-sky-note-artwork-placeholder="true"\s+data-artwork-descriptor="[^"]*">.*?</figure>', flags=re.S)
PUBLISHED_RE = re.compile(r'<figure class="sky-note-artwork"[^>]*>.*?</figure>', flags=re.S)
RELATED_RE = re.compile(r'<div class="related-descriptor-artwork"\s+data-related-descriptor-artwork="true">.*?</div>', flags=re.S)


def descriptor_artwork(records: list[dict]) -> str:
    cards = []
    for record in records:
        if record.get("type") not in {"star", "deep-sky-object"}:
            continue
        related_id = str(record.get("id", ""))
        if not related_id.isdigit():
            continue
        artwork = ARTWORK_ROOT / related_id / "finder.svg"
        if not artwork.exists():
            continue
        href = f"../../../sky-notes-artwork/objects/{related_id}/finder.svg"
        descriptor_href = f"../../../almanack/descriptors/{related_id}.json"
        name = html.escape(str(record.get("name") or related_id))
        cards.append(
            f'<figure class="descriptor-artwork" data-descriptor-id="{related_id}">'
            f'<a href="{href}"><img src="{href}" alt="Stellar finder for {name}" loading="lazy"></a>'
            f'<figcaption><a href="{descriptor_href}" type="application/json">{name}</a></figcaption></figure>'
        )
    if not cards:
        return ""
    return (
        '<div class="related-descriptor-artwork" data-related-descriptor-artwork="true">'
        '<p>Related machine-readable descriptors:</p>' + "".join(cards) + '</div>'
    )


def publish_page(path: Path, records: list[dict]) -> bool:
    text = path.read_text(encoding="utf-8")
    # Remove the obsolete week-owned finder. Weekly pages now aggregate only
    # immutable object-owned artwork.
    new = PUBLISHED_RE.sub("", text)
    new = RELATED_RE.sub("", new)
    related = descriptor_artwork(records)
    placeholder = PLACEHOLDER_RE.search(new)
    if placeholder is not None:
        new = new[:placeholder.start()] + related + new[placeholder.end():]
    elif related:
        marker = '</div></div><div class="almanack-bottom-nav-wrap"'
        if marker not in new:
            raise RuntimeError(f"Missing Sky Notes publication anchor in {path.relative_to(ROOT)}")
        new = new.replace(marker, related + marker, 1)
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
        records = json.loads(payload_path.read_text(encoding="utf-8")).get("descriptors") or []
        published += 1
        for root in PAGE_ROOTS:
            page = root / str(item.year) / week_key / "index.html"
            if not page.exists():
                raise RuntimeError(f"Weekly page is missing: {page.relative_to(ROOT)}")
            if publish_page(page, records):
                changed += 1
    print(f"Published object-owned artwork for {start.isoformat()} through {end.isoformat()}: {published} weeks, {changed} page copies updated")


if __name__ == "__main__":
    main()
