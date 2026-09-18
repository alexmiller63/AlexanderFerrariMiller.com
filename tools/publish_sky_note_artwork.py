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
SPEC_ROOT = ROOT / "sky-notes-artwork" / "specs"

PLACEHOLDER_RE = re.compile(r'<figure class="sky-note-artwork-placeholder"\s+data-sky-note-artwork-placeholder="true"\s+data-artwork-descriptor="[^"]*">.*?</figure>', flags=re.S)
PUBLISHED_RE = re.compile(r'<figure class="sky-note-artwork">.*?</figure>', flags=re.S)


def load_descriptor(year: int, week: int) -> dict:
    source = DESCRIPTOR_ROOT / str(year) / f"W{week:02d}.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    descriptor = payload.get("artwork")
    if not isinstance(descriptor, dict):
        raise RuntimeError(f"{source.relative_to(ROOT)} has no artwork descriptor")
    return descriptor


def object_id_for_week(year: int, week: int) -> int:
    spec_path = SPEC_ROOT / str(year) / f"W{week:02d}.json"
    if not spec_path.exists():
        raise RuntimeError(f"Missing renderer spec {spec_path.relative_to(ROOT)}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    identity = spec.get("artwork_owner_identity") or {}
    fixed_id = identity.get("fixed_object_id")
    if not isinstance(fixed_id, int):
        raise RuntimeError(f"{spec_path.relative_to(ROOT)} has no immutable artwork-owner fixed_object_id")
    return fixed_id


def published_figure(fixed_id: int, descriptor: dict) -> str:
    href = f"../../../sky-notes-artwork/objects/{fixed_id}/finder.svg"
    constellation = descriptor.get("constellation") or "the sky"
    asterism = descriptor.get("asterism") or {}
    subject = f"{asterism.get('name')} in {constellation}" if asterism.get("name") else constellation
    targets = [str(item.get("name")) for item in descriptor.get("targets", []) if item.get("name")]
    target_text = ", ".join(targets) if targets else f"fixed object {fixed_id}"
    alt = html.escape(f"Sky Note stellar finder for {subject}; highlighting {target_text}", quote=True)
    caption = html.escape(f"Stellar finder: {subject}; highlight {target_text}.")
    descriptor_href = f"../../../almanack/descriptors/{fixed_id}.json"
    return ('<figure class="sky-note-artwork" data-descriptor-id="' + str(fixed_id) + '">'
            f'<a class="sky-note-artwork-link" href="{href}"><img src="{href}" alt="{alt}" loading="lazy"></a>'
            f'<figcaption>{caption} <a href="{descriptor_href}" type="application/json">Descriptor</a> · <a href="{href}">Artwork</a></figcaption>'
            '</figure>')


def publish_page(path: Path, fixed_id: int, descriptor: dict, records: list[dict]) -> bool:
    text = path.read_text(encoding="utf-8")
    replacement = published_figure(fixed_id, descriptor)
    placeholder = PLACEHOLDER_RE.search(text)
    published = PUBLISHED_RE.search(text)
    match = placeholder if placeholder is not None else published
    if match is None:
        raise RuntimeError(f"Missing Sky Note artwork publication slot in {path.relative_to(ROOT)}")
    new = text[:match.start()] + replacement + text[match.end():]
    cards = []
    for record in records:
        if record.get("type") not in {"star", "deep-sky-object"}:
            continue
        related_id = str(record.get("id", ""))
        if not related_id.isdigit() or int(related_id) == fixed_id:
            continue
        artwork = ARTWORK_ROOT / related_id / "finder.svg"
        if not artwork.exists():
            continue
        href = f"../../../sky-notes-artwork/objects/{related_id}/finder.svg"
        name = html.escape(str(record.get("name") or related_id))
        cards.append(
            f'<figure class="descriptor-artwork" data-descriptor-id="{related_id}">'
            f'<a href="{href}"><img src="{href}" alt="Stellar finder for {name}" loading="lazy"></a>'
            f'<figcaption><a href="../../../almanack/descriptors/{related_id}.json" type="application/json">{name}</a></figcaption></figure>'
        )
        if len(cards) == 6:
            break
    if cards and 'data-related-descriptor-artwork="true"' not in new:
        related = (
            '<div class="related-descriptor-artwork" data-related-descriptor-artwork="true">'
            '<p>Related machine-readable descriptors:</p>' + "".join(cards) + '</div>'
        )
        anchor = PUBLISHED_RE.search(new)
        if anchor is None:
            raise RuntimeError(f"Missing published Artwork anchor in {path.relative_to(ROOT)}")
        new = new[:anchor.start()] + related + new[anchor.start():]
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main() -> None:
    start, end, weeks = parse_range_args("Publish fixed-object-owned Star Almanack Sky Note artwork")
    changed = published = skipped = 0
    for item in weeks:
        week_key = f"W{item.week:02d}"
        spec = SPEC_ROOT / str(item.year) / f"{week_key}.json"
        if not spec.exists():
            print(f"No renderer spec for {item.year}-{week_key}; skipping publication")
            skipped += 1
            continue
        fixed_id = object_id_for_week(item.year, item.week)
        artwork = ARTWORK_ROOT / str(fixed_id) / "finder.svg"
        if not artwork.exists():
            print(f"No rendered artwork for fixed object {fixed_id}; skipping {item.year}-{week_key}")
            skipped += 1
            continue
        descriptor = load_descriptor(item.year, item.week)
        payload_path = DESCRIPTOR_ROOT / str(item.year) / f"{week_key}.json"
        records = json.loads(payload_path.read_text(encoding="utf-8")).get("descriptors") or []
        published += 1
        for root in PAGE_ROOTS:
            page = root / str(item.year) / week_key / "index.html"
            if not page.exists():
                raise RuntimeError(f"Weekly page is missing: {page.relative_to(ROOT)}")
            if publish_page(page, fixed_id, descriptor, records):
                changed += 1
    print(f"Published fixed-object artwork for {start.isoformat()} through {end.isoformat()}: {published} weeks, {skipped} skipped, {changed} page copies updated")


if __name__ == "__main__":
    main()
