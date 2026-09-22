#!/usr/bin/env python3
"""Publish fixed-object-owned Sky Note finders into generated weekly pages."""
from __future__ import annotations

import re
from pathlib import Path

from iso_date_range import parse_range_args
from almanack_paths import week_index

ROOT = Path(__file__).resolve().parents[1]
ARTWORK_ROOT = ROOT / "sky-notes-artwork" / "objects"
DESCRIPTOR_ROOT = ROOT / "generated-sky-notes"

PLACEHOLDER_RE = re.compile(r'<figure class="sky-note-artwork-placeholder"\s+data-sky-note-artwork-placeholder="true"\s+data-artwork-descriptor="[^"]*">.*?</figure>', flags=re.S)
PUBLISHED_RE = re.compile(r'<figure class="sky-note-artwork"[^>]*>.*?</figure>', flags=re.S)
RELATED_RE = re.compile(r'<div class="related-descriptor-artwork"\s+data-related-descriptor-artwork="true">.*?</div>', flags=re.S)


def publish_page(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    # Remove the obsolete week-owned finder. Weekly pages now aggregate only
    # immutable object-owned artwork.
    new = PUBLISHED_RE.sub("", text)
    new = RELATED_RE.sub("", new)
    # Artwork publication must not infer semantic relationships from the weekly
    # descriptor collection. Sky Notes owns object membership/relationships.
    new = PLACEHOLDER_RE.sub("", new)
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
        published += 1
        page = week_index(item.year, item.week)
        if not page.exists():
            raise RuntimeError(f"Weekly page is missing: {page.relative_to(ROOT)}")
        if publish_page(page):
            changed += 1
    print(f"Published object-owned artwork for {start.isoformat()} through {end.isoformat()}: {published} weeks, {changed} page copies updated")


if __name__ == "__main__":
    main()
