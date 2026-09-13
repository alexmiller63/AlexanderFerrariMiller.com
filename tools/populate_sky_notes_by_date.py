#!/usr/bin/env python3
"""Create and populate Sky Note prose for ISO weeks in an inclusive date range.

Existing curated Sky Notes remain authoritative. If a requested week has no
curated source, this generator creates a deterministic observer-first draft
from that week's Calendar data and saves it as a modular source file.

Artwork is deliberately preserved and is owned by
populate_sky_notes_artwork_by_date.py.
"""
from __future__ import annotations

import html
import importlib.util
import json
import re
from datetime import date
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


def plain_text(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", " · ", fragment, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def calendar_events_from_page(path: Path) -> list[tuple[date, list[str]]]:
    text = path.read_text(encoding="utf-8")
    result: list[tuple[date, list[str]]] = []
    for row in re.finditer(r'<tr[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*>(.*?)</tr>', text, flags=re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row.group(2), flags=re.S)
        if not cells:
            continue
        raw_events = cells[-1]
        entries = []
        for part in re.split(r"<br\s*/?>", raw_events, flags=re.I):
            cleaned = plain_text(part)
            if cleaned and cleaned != "—":
                entries.append(cleaned)
        result.append((date.fromisoformat(row.group(1)), entries))
    if not result:
        raise RuntimeError(f"Could not read machine-readable Calendar rows from {path.relative_to(ROOT)}")
    return result


def first_matching(entries: list[str], pattern: str) -> str | None:
    regex = re.compile(pattern, flags=re.I)
    return next((entry for entry in entries if regex.search(entry)), None)


def generated_note(year: int, week: int, page_path: Path) -> dict:
    rows = calendar_events_from_page(page_path)
    monday, sunday = rows[0][0], rows[-1][0]
    entries = [entry for _, items in rows for entry in items]

    moon = first_matching(entries, r"\b(New Moon|First Quarter|Full Moon|Last Quarter)\b")
    messier = [entry for entry in entries if re.search(r"(?<![A-Za-z0-9])M(?:110|10\d|[1-9]\d?)(?!\d)", entry)]
    naked = [entry for entry in entries if "👁" in entry]
    binocular = [entry for entry in entries if re.search(r"\bB\s+V\b", entry)]
    solar = [entry for entry in entries if "Sun enters " in entry or "Wheel of the Year:" in entry]

    highlights = []
    for candidate in ([moon] if moon else []) + solar + naked + messier + binocular:
        if candidate and candidate not in highlights:
            highlights.append(candidate)
        if len(highlights) == 3:
            break

    if highlights:
        opening = (
            f"ISO {year}-W{week:02d} runs from {monday.strftime('%B')} {monday.day} through "
            f"{sunday.strftime('%B')} {sunday.day}. Calendar highlights include "
            + "; ".join(highlights)
            + "."
        )
    else:
        opening = (
            f"ISO {year}-W{week:02d} runs from {monday.strftime('%B')} {monday.day} through "
            f"{sunday.strftime('%B')} {sunday.day}. The Calendar has no major named event this week, "
            "so use the seasonal star field and the weekly Solar-System ephemeris as the observing framework."
        )

    moon_text = moon or "No principal lunar phase is listed in this week"
    if moon and "New Moon" in moon:
        condition = "The dark Moon favors faint targets and extended star fields."
    elif moon and "Full Moon" in moon:
        condition = "Bright moonlight favors prominent stars and planets while reducing contrast on faint deep-sky objects."
    elif moon:
        condition = "Moderate moonlight makes timing and local sky position important for faint targets."
    else:
        condition = "Check the Moon's position each night and favor darker hours for low-contrast targets."

    naked_targets = "; ".join(naked[:2]) if naked else "Use the brightest seasonal stars and the zodiac as orientation anchors."
    binocular_targets = "; ".join((messier + binocular)[:2]) if (messier or binocular) else "Use binoculars to widen the field around the week's brightest Calendar targets."
    telescope_targets = "; ".join(messier[:2]) if messier else "Use the weekly ephemeris to choose planets and other compact targets that are well separated from the Sun."

    note = "\n\n".join(
        (
            opening,
            f"**Naked eye:** {moon_text}. {condition} {naked_targets}",
            f"**Binoculars:** {binocular_targets}",
            f"**Small telescope:** {telescope_targets}",
        )
    )
    return {
        "week": f"W{week:02d}",
        "title": f"Observer’s guide for ISO {year}-W{week:02d}",
        "status": "generated-draft",
        "note": note,
    }


def save_generated_source(year: int, week: int, payload: dict) -> Path:
    directory = SOURCE_ROOT / f"sky-notes-{year}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"W{week:02d}.json"
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing Sky Note source: {path.relative_to(ROOT)}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


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
    start, end, weeks = parse_range_args("Create and populate Star Almanack Sky Notes prose by inclusive ISO date range")
    catalogs: dict[int, dict[str, dict]] = {}
    changed = 0
    created = 0

    for item in weeks:
        if item.year not in catalogs:
            catalogs[item.year] = load_year(item.year)
        week_key = f"W{item.week:02d}"
        payload = catalogs[item.year].get(week_key)

        public_page = ROOT / "almanack" / str(item.year) / week_key / "index.html"
        if not public_page.exists():
            raise RuntimeError(f"Missing weekly page: {public_page.relative_to(ROOT)}")

        if payload is None:
            payload = generated_note(item.year, item.week, public_page)
            source = save_generated_source(item.year, item.week, payload)
            catalogs[item.year][week_key] = payload
            created += 1
            print(f"Created Sky Note source for ISO {item.year}-{week_key}: {source.relative_to(ROOT)}")

        note = payload.get("note", "").strip()
        if not note:
            raise RuntimeError(f"Empty Sky Note for ISO {item.year}-{week_key}")

        for root in PAGE_ROOTS:
            path = root / str(item.year) / week_key / "index.html"
            if not path.exists():
                raise RuntimeError(f"Missing weekly page: {path.relative_to(ROOT)}")
            if patch_page(path, note):
                changed += 1
        status = payload.get("status", "curated")
        print(f"Populated Sky Note prose for ISO {item.year}-{week_key} ({status})")

    print(
        f"Sky Notes prose complete for {start.isoformat()} through {end.isoformat()}: "
        f"{created} sources created, {changed} page copies updated"
    )


if __name__ == "__main__":
    main()
