#!/usr/bin/env python3
"""Populate requested Almanack years with core asterism events."""
from __future__ import annotations

import csv
import datetime as dt
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
PUBLIC = ROOT / "almanack"
SOURCE_SITE = SRC / "site"
DEFAULT_YEARS = (2025, 2027)


def requested_years() -> tuple[int, ...]:
    if len(sys.argv) == 1:
        return DEFAULT_YEARS
    try:
        years = tuple(dict.fromkeys(int(x) for x in sys.argv[1:]))
    except ValueError as exc:
        raise SystemExit("Years must be integers, e.g. 2025 2027") from exc
    if any(y < 1 for y in years):
        raise SystemExit("Years must be positive integers")
    return years


def read_rows(year: int) -> list[dict[str, str]]:
    path = SRC / f"asterism-geometry-{year}.csv"
    if not path.exists():
        raise SystemExit(f"Missing asterism geometry source for {year}: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 25:
        raise SystemExit(f"Expected 25 asterism rows for {year}, got {len(rows)}")
    if len({r['asterism'] for r in rows}) != 25:
        raise SystemExit(f"Duplicate/missing asterism names for {year}")
    return rows


def event_map(rows: list[dict[str, str]]) -> dict[dt.date, list[str]]:
    events: dict[dt.date, list[str]] = defaultdict(list)
    for r in rows:
        d = dt.date.fromisoformat(r["best_date"])
        events[d].append(f"✦ {r['asterism']} asterism")
    return events


def date_pattern(d: dt.date) -> str:
    return rf"{d.strftime('%a, %b ')}0?{d.day}, {d.year}"


def pages_for_events(root: Path, events: dict[dt.date, list[str]]) -> list[Path]:
    pages: list[Path] = []
    for iso_year in sorted({d.isocalendar().year for d in events}):
        pages.extend(sorted((root / str(iso_year)).glob("W*/index.html")))
    return pages


def inject(root: Path, events: dict[dt.date, list[str]]) -> tuple[int, int]:
    changed = inserted = 0
    for page in pages_for_events(root, events):
        text = page.read_text(encoding="utf-8"); original = text
        text = text.replace(" asterism observance", " asterism")
        for d, vals in events.items():
            pat = re.compile(rf"(<tr><td>{date_pattern(d)}</td><td>.*?</td><td>)(.*?)(</td></tr>)")
            m = pat.search(text)
            if not m: continue
            keep = [] if m.group(2) == "—" else [x for x in m.group(2).split("<br>") if x]
            before = len(keep)
            for v in vals:
                if v not in keep: keep.append(v)
            inserted += len(keep) - before
            text = text[:m.start(2)] + "<br>".join(keep) + text[m.end(2):]
        if text != original: page.write_text(text, encoding="utf-8"); changed += 1
    return changed, inserted


def validate(root: Path, events: dict[dt.date, list[str]]) -> None:
    page_texts = [(page, page.read_text(encoding="utf-8")) for page in pages_for_events(root, events)]
    for d, vals in events.items():
        pat = re.compile(rf"<tr><td>{date_pattern(d)}</td><td>.*?</td><td>(.*?)</td></tr>")
        matches = [(page, m.group(1)) for page, text in page_texts for m in pat.finditer(text)]
        if len(matches) != 1:
            raise SystemExit(f"{root}: expected exactly one calendar row for {d}, found {len(matches)}")
        page, cell = matches[0]
        for v in vals:
            count = cell.split("<br>").count(v)
            if count != 1:
                raise SystemExit(f"{root}: expected {v!r} exactly once on {d} in {page}, found {count}")


def main() -> None:
    for year in requested_years():
        rows = read_rows(year); events = event_map(rows)
        c1, i1 = inject(SOURCE_SITE, events); c2, i2 = inject(PUBLIC, events)
        validate(SOURCE_SITE, events); validate(PUBLIC, events)
        print(f"{year}: verified 25 asterisms exactly once in each tree; inserted source={i1}, public={i2}; updated {c1} source + {c2} public pages")

if __name__ == "__main__": main()
