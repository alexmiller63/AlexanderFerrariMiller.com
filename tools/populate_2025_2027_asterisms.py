#!/usr/bin/env python3
"""Populate 2025/2027 weekly calendars with core asterism observances."""
from __future__ import annotations

import csv
import datetime as dt
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
PUBLIC = ROOT / "almanack"
SOURCE_SITE = SRC / "site"
YEARS = (2025, 2027)


def read_rows(year: int) -> list[dict[str, str]]:
    path = SRC / f"asterism-geometry-{year}.csv"
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
        events[d].append(f"✦ {r['asterism']} asterism observance")
    return events


def date_pattern(d: dt.date) -> str:
    """Match both 'Jan 1' and 'Jan 01' calendar date styles."""
    return rf"{d.strftime('%a, %b ')}0?{d.day}, {d.year}"


def inject(root: Path, events: dict[dt.date, list[str]]) -> tuple[int, int]:
    changed = 0
    inserted = 0
    iso_years = sorted({d.isocalendar().year for d in events})
    pages = []
    for iso_year in iso_years:
        pages.extend(sorted((root / str(iso_year)).glob("W*/index.html")))

    for page in pages:
        text = page.read_text(encoding="utf-8")
        original = text
        for d, vals in events.items():
            pat = re.compile(
                rf"(<tr><td>{date_pattern(d)}</td><td>.*?</td><td>)(.*?)(</td></tr>)"
            )
            m = pat.search(text)
            if not m:
                continue
            keep = [] if m.group(2) == "—" else [x for x in m.group(2).split("<br>") if x]
            before = len(keep)
            for v in vals:
                if v not in keep:
                    keep.append(v)
            inserted += len(keep) - before
            text = text[:m.start(2)] + "<br>".join(keep) + text[m.end(2):]
        if text != original:
            page.write_text(text, encoding="utf-8")
            changed += 1
    return changed, inserted


def main() -> None:
    for year in YEARS:
        rows = read_rows(year)
        events = event_map(rows)
        c1, i1 = inject(SOURCE_SITE, events)
        c2, i2 = inject(PUBLIC, events)
        if i1 != 25 or i2 != 25:
            raise SystemExit(
                f"{year}: expected 25 inserted observances in each tree, got source={i1}, public={i2}"
            )
        print(f"{year}: inserted 25 asterism observances; updated {c1} source + {c2} public pages")


if __name__ == "__main__":
    main()
