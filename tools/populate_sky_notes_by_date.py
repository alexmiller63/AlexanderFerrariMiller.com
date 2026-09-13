#!/usr/bin/env python3
"""Populate only Sky Note prose for ISO weeks in an inclusive date range.

Artwork is deliberately preserved and is owned by populate_sky_notes_artwork_by_date.py.
"""
from __future__ import annotations

import html
import importlib.util
import json
import re
from pathlib import Path

from iso_date_range import parse_range_args

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Star-Almanack-Repo"
PAGE_ROOTS = (ROOT / "Star-Almanack-Repo" / "site", ROOT / "almanack")


def load_legacy_2026():
    path = SOURCE_ROOT / "apply_sky_notes.py"
    spec = importlib.util.spec_from_file_location("legacy_apply_sky_notes_2026", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path.relative_to(ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    weeks = module.load_notes()
    messier = module.load_messier_catalog()
    rendered = {}
    for week, payload in weeks.items():
        note = payload.get("note", "").strip()
        note = module.enrich_observer_note(week, note)
        note = module.expand_messier_mentions(note, messier)
        rendered[week] = {**payload, "note": note}
    return rendered


def load_generic_year(year: int) -> dict[str, dict]:
    catalog = SOURCE_ROOT / f"sky-notes-{year}.json"
    modular = SOURCE_ROOT / f"sky-notes-{year}"
    weeks: dict[str, dict] = {}
    if catalog.exists():
        payload = json.loads(catalog.read_text(encoding="utf-8"))
        weeks.update(payload.get("weeks", {}))
    if modular.exists():
        for path in sorted(modular.glob("W[0-5][0-9].json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            week = path.stem
            declared = payload.get("week", week)
            if declared != week:
                raise RuntimeError(f"Week mismatch in {path.relative_to(ROOT)}: {declared} != {week}")
            if week in weeks:
                raise RuntimeError(f"Duplicate Sky Note source for {year}-{week}")
            weeks[week] = payload
    return weeks


def load_year(year: int) -> dict[str, dict]:
    if year == 2026 and (SOURCE_ROOT / "apply_sky_notes.py").exists():
        return load_legacy_2026()
    return load_generic_year(year)


def inline_markup(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    return escaped


def render_note(note: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", note.strip()) if part.strip()]
    return [f"<p>{inline_markup(' '.join(part.splitlines()))}</p>" for part in paragraphs]


def sky_note_bounds(text: str, path: Path) -> tuple[int, int, int]:
    marker = "<h3>Sky Note</h3>"
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"Missing Sky Note heading in {path.relative_to(ROOT)}")
    body_start = start + len(marker)
    match = re.search(r"<h[23]>.*?</h[23]>", text[body_start:], flags=re.S)
    end = body_start + match.start() if match else text.find("</main>", body_start)
    if end < 0:
        end = len(text)
    return start, body_start, end


def patch_page(path: Path, note: str) -> bool:
    text = path.read_text(encoding="utf-8")
    _, body_start, end = sky_note_bounds(text, path)
    body = text[body_start:end]
    new_paragraphs = render_note(note)

    # Artwork belongs to another generator. If artwork is present, replace only
    # prose paragraphs in place so figure nodes, comments, and placement survive.
    has_artwork = "<figure" in body or "data-sky-note-artwork=" in body or "SKY-NOTE-ARTWORK" in body
    if has_artwork:
        matches = list(re.finditer(r"<p>.*?</p>", body, flags=re.S))
        if len(matches) != len(new_paragraphs):
            raise RuntimeError(
                f"Refusing to disturb Sky Note artwork in {path.relative_to(ROOT)}: "
                f"existing prose has {len(matches)} paragraphs, source has {len(new_paragraphs)}"
            )
        iterator = iter(new_paragraphs)
        new_body = re.sub(r"<p>.*?</p>", lambda _: next(iterator), body, flags=re.S)
    else:
        new_body = "\n" + "\n".join(new_paragraphs) + "\n"

    new = text[:body_start] + new_body + text[end:]
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main() -> None:
    start, end, weeks = parse_range_args("Populate Star Almanack Sky Notes prose by inclusive ISO date range")
    catalogs: dict[int, dict[str, dict]] = {}
    changed = 0

    for item in weeks:
        if item.year not in catalogs:
            catalogs[item.year] = load_year(item.year)
        week_key = f"W{item.week:02d}"
        payload = catalogs[item.year].get(week_key)
        if payload is None:
            raise RuntimeError(
                f"No curated Sky Note source for ISO {item.year}-{week_key}. "
                f"Create Star-Almanack-Repo/sky-notes-{item.year}.json or "
                f"Star-Almanack-Repo/sky-notes-{item.year}/{week_key}.json first."
            )
        note = payload.get("note", "").strip()
        if not note:
            raise RuntimeError(f"Empty curated Sky Note for ISO {item.year}-{week_key}")

        for root in PAGE_ROOTS:
            path = root / str(item.year) / week_key / "index.html"
            if not path.exists():
                raise RuntimeError(f"Missing weekly page: {path.relative_to(ROOT)}")
            if patch_page(path, note):
                changed += 1
        print(f"Populated Sky Note prose for ISO {item.year}-{week_key}")

    print(f"Sky Notes prose complete for {start.isoformat()} through {end.isoformat()}: {changed} page copies updated")


if __name__ == "__main__":
    main()
