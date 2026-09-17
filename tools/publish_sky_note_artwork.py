#!/usr/bin/env python3
"""Replace Sky Note artwork placeholders with the rendered weekly finder.

This is the publication half of the Artwork Generator: the descriptor-first Sky
Notes generator emits the structured request, the renderer creates finder.svg,
and this step wires the published weekly pages to that rendered artifact.  It
never changes story or machine-descriptor links.
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

PLACEHOLDER_RE = re.compile(
    r'<figure class="sky-note-artwork-placeholder"\s+'
    r'data-sky-note-artwork-placeholder="true"\s+'
    r'data-artwork-descriptor="(?P<descriptor>[^"]*)">.*?</figure>',
    flags=re.S,
)


def published_figure(year: int, week: int, descriptor: dict) -> str:
    href = f"/sky-notes-artwork/{year}/W{week:02d}/finder.svg"
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


def publish_page(path: Path, year: int, week: int) -> bool:
    text = path.read_text(encoding="utf-8")
    match = PLACEHOLDER_RE.search(text)
    if match is None:
        raise RuntimeError(f"Missing Sky Note artwork placeholder in {path.relative_to(ROOT)}")
    descriptor = json.loads(html.unescape(match.group("descriptor")))
    replacement = published_figure(year, week, descriptor)
    new = text[:match.start()] + replacement + text[match.end():]
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main() -> None:
    start, end, weeks = parse_range_args("Publish rendered Star Almanack Sky Note artwork by inclusive ISO date range")
    changed = 0
    for item in weeks:
        week_key = f"W{item.week:02d}"
        artwork = ARTWORK_ROOT / str(item.year) / week_key / "finder.svg"
        if not artwork.exists():
            raise RuntimeError(f"Rendered artwork is missing: {artwork.relative_to(ROOT)}")
        for root in PAGE_ROOTS:
            page = root / str(item.year) / week_key / "index.html"
            if not page.exists():
                raise RuntimeError(f"Weekly page is missing: {page.relative_to(ROOT)}")
            if publish_page(page, item.year, item.week):
                changed += 1
    print(f"Published Sky Note artwork for {start.isoformat()} through {end.isoformat()}: {changed} page copies updated")


if __name__ == "__main__":
    main()
