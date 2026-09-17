#!/usr/bin/env python3
"""Publish rendered weekly Sky Note finders into generated weekly pages.

This is the publication half of the Artwork Generator.  The descriptor-first
Sky Notes generator owns the artwork request, the artwork generator renders the
finder, and this step wires that rendered artifact into both weekly page trees.

Publication is deliberately idempotent: a fresh Sky Notes page contains an
artwork placeholder, while a page from an earlier successful Artwork run
contains an already-published artwork figure.  Either state is a valid input.
The generated Sky Note JSON remains the source of truth for the descriptor, so
rerunning Artwork never requires regenerating Sky Notes merely to recreate a
consumed placeholder.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from iso_date_range import parse_range_args

ROOT = Path(__file__).resolve().parents[1]
PAGE_ROOTS = (ROOT / "site", ROOT / "almanack")
ARTWORK_ROOT = ROOT / "sky-notes-artwork"
DESCRIPTOR_ROOT = ROOT / "generated-sky-notes"

PLACEHOLDER_RE = re.compile(
    r'<figure class="sky-note-artwork-placeholder"\s+'
    r'data-sky-note-artwork-placeholder="true"\s+'
    r'data-artwork-descriptor="[^"]*">.*?</figure>',
    flags=re.S,
)
PUBLISHED_RE = re.compile(
    r'<figure class="sky-note-artwork">.*?</figure>',
    flags=re.S,
)


def load_descriptor(year: int, week: int) -> dict:
    source = DESCRIPTOR_ROOT / str(year) / f"W{week:02d}.json"
    if not source.exists():
        raise RuntimeError(
            f"Missing generated Sky Note source {source.relative_to(ROOT)}. "
            "Run Populate Sky Notes first."
        )
    payload = json.loads(source.read_text(encoding="utf-8"))
    descriptor = payload.get("artwork")
    if not isinstance(descriptor, dict):
        raise RuntimeError(
            f"Rendered artwork exists for {year}-W{week:02d}, but "
            f"{source.relative_to(ROOT)} has no artwork descriptor"
        )
    return descriptor


def published_figure(year: int, week: int, descriptor: dict) -> str:
    # Weekly pages live two directories below their page-tree root.  Use a
    # relative URL so the link works both on the custom domain and on GitHub
    # Pages' project-site prefix (/AlexanderFerrariMiller.com/).
    href = f"../../../sky-notes-artwork/{year}/W{week:02d}/finder.svg"
    constellation = descriptor.get("constellation") or "the weekly sky"
    asterism = descriptor.get("asterism") or {}
    subject = f"{asterism.get('name')} in {constellation}" if asterism.get("name") else constellation
    targets = [str(item.get("name")) for item in descriptor.get("targets", []) if item.get("name")]
    target_text = ", ".join(targets) if targets else "weekly observing targets"
    alt = html.escape(f"Sky Note stellar finder for {subject}; highlighting {target_text}", quote=True)
    caption = html.escape(f"Stellar finder: {subject}; highlight {target_text}.")
    return (
        '<figure class="sky-note-artwork">'
        f'<a class="sky-note-artwork-link" href="{href}"><img src="{href}" alt="{alt}" loading="lazy"></a>'
        f'<figcaption>{caption} <a href="{href}">Artwork</a></figcaption>'
        '</figure>'
    )


def publish_page(path: Path, year: int, week: int, descriptor: dict) -> bool:
    text = path.read_text(encoding="utf-8")
    replacement = published_figure(year, week, descriptor)

    placeholder = PLACEHOLDER_RE.search(text)
    published = PUBLISHED_RE.search(text)
    if placeholder is not None:
        match = placeholder
    elif published is not None:
        match = published
    else:
        raise RuntimeError(
            f"Missing Sky Note artwork publication slot in {path.relative_to(ROOT)}: "
            "expected either a fresh placeholder or an existing published artwork figure"
        )

    new = text[:match.start()] + replacement + text[match.end():]
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main() -> None:
    start, end, weeks = parse_range_args("Publish rendered Star Almanack Sky Note artwork by inclusive ISO date range")
    changed = 0
    published = 0
    skipped = 0
    for item in weeks:
        week_key = f"W{item.week:02d}"
        artwork = ARTWORK_ROOT / str(item.year) / week_key / "finder.svg"
        if not artwork.exists():
            print(f"No rendered artwork for {item.year}-{week_key}; skipping publication")
            skipped += 1
            continue

        descriptor = load_descriptor(item.year, item.week)
        published += 1
        for root in PAGE_ROOTS:
            page = root / str(item.year) / week_key / "index.html"
            if not page.exists():
                raise RuntimeError(f"Weekly page is missing: {page.relative_to(ROOT)}")
            if publish_page(page, item.year, item.week, descriptor):
                changed += 1

    print(
        f"Published Sky Note artwork for {start.isoformat()} through {end.isoformat()}: "
        f"{published} rendered weeks, {skipped} unrendered weeks skipped, "
        f"{changed} page copies updated"
    )


if __name__ == "__main__":
    main()
