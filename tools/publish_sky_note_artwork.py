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


def publish_page(path: Path, payload: dict, year: int, week: int) -> bool:
    text = path.read_text(encoding="utf-8")
    new = PUBLISHED_RE.sub("", text)
    new = RELATED_RE.sub("", new)
    new = PLACEHOLDER_RE.sub("", new)
    descriptor = payload.get("planet_finder_artwork")
    if descriptor:
        route = descriptor.get("finder_route") or {}
        planet = str(route.get("planet") or "Planet")
        reference = str(route.get("reference_star") or "")
        svg = ARTWORK_ROOT / str(year) / f"W{week:02d}" / "planet-finder.svg"
        if not svg.exists():
            raise RuntimeError(f"Planet finder SVG is missing: {svg.relative_to(ROOT)}")
        figure = (
            '<figure class="sky-note-artwork planet-finder-artwork" data-planet-finder="true">'
            f'<img src="/sky-notes-artwork/weeks/{year}/W{week:02d}/planet-finder.svg" '
            f'alt="{html.escape(planet)} finder chart using {html.escape(reference)} as the reference star">'
            f'<figcaption>Finder chart: {html.escape(planet)} from {html.escape(reference)}.</figcaption>'
            '</figure>'
        )
        marker = '<div class="sky-note-wordy">'
        if marker not in new:
            raise RuntimeError("Sky Notes Wordy container is missing")
        new = new.replace(marker, marker + figure, 1)
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
