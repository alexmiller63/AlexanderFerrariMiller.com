#!/usr/bin/env python3
"""Audit that generated Almanack editions are genuinely parameterized by year.

This is deliberately an edition audit, not an astronomy regression.  It checks
that generated weekly pages and generated visibility tables belong to their
requested ISO year instead of silently carrying copied 2026 placement data.
"""
from __future__ import annotations

import csv
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "almanack"
SOURCE_SITE = ROOT / "Star-Almanack-Repo" / "site"
GENERATED = ROOT / "Star-Almanack-Repo" / "generated"
DEFAULT_YEARS = (2025, 2027)

DATE_CELL_RE = re.compile(r"<tr><td>([A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}, \d{4})</td>")
ISO_WEEK_RE = re.compile(r"ISO (\d{4})-W(\d{2})")
DATE_COLUMNS = ("best_date", "center_best_date", "date")


def requested_years() -> tuple[int, ...]:
    if len(sys.argv) == 1:
        return DEFAULT_YEARS
    try:
        return tuple(dict.fromkeys(int(x) for x in sys.argv[1:]))
    except ValueError as exc:
        raise SystemExit("Years must be integers, e.g. 2025 2027") from exc


def parse_calendar_date(text: str) -> dt.date:
    return dt.datetime.strptime(text, "%a, %b %d, %Y").date()


def audit_week_pages(root: Path, year: int) -> tuple[int, list[str]]:
    pages = sorted((root / str(year)).glob("W??/index.html"))
    failures: list[str] = []
    if not pages:
        return 0, [f"no weekly pages under {root / str(year)}"]

    for page in pages:
        week = int(page.parent.name[1:])
        text = page.read_text(encoding="utf-8")

        labels = [(int(y), int(w)) for y, w in ISO_WEEK_RE.findall(text)]
        if (year, week) not in labels:
            failures.append(f"{page}: missing ISO {year}-W{week:02d} page label")
        wrong = sorted({(y, w) for y, w in labels if y != year})
        if wrong:
            failures.append(f"{page}: foreign ISO week labels {wrong}")

        cells = DATE_CELL_RE.findall(text)
        if not cells:
            failures.append(f"{page}: no calendar date rows found")
            continue
        for raw in cells:
            day = parse_calendar_date(raw)
            iso = day.isocalendar()
            if iso.year != year or iso.week != week:
                failures.append(
                    f"{page}: {day.isoformat()} belongs to ISO {iso.year}-W{iso.week:02d}, "
                    f"not ISO {year}-W{week:02d}"
                )
    return len(pages), failures


def audit_generated_csv(path: Path, year: int) -> list[str]:
    failures: list[str] = []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return [f"{path}: generated CSV is empty"]

    date_column = next((name for name in DATE_COLUMNS if name in rows[0]), None)
    if date_column is None:
        return failures

    for n, row in enumerate(rows, start=2):
        raw = (row.get(date_column) or "").strip()
        if not raw:
            continue
        try:
            day = dt.date.fromisoformat(raw[:10])
        except ValueError:
            failures.append(f"{path}:{n}: invalid {date_column}={raw!r}")
            continue
        if day.isocalendar().year != year:
            failures.append(
                f"{path}:{n}: {date_column} {day.isoformat()} belongs to ISO "
                f"{day.isocalendar().year}, expected {year}"
            )
    return failures


def audit_year(year: int) -> list[str]:
    failures: list[str] = []
    counts = []
    for root in (SOURCE_SITE, PUBLIC):
        count, page_failures = audit_week_pages(root, year)
        counts.append(count)
        failures.extend(page_failures)

    for path in sorted(GENERATED.glob(f"*-{year}.csv")):
        failures.extend(audit_generated_csv(path, year))

    if not failures:
        print(
            f"{year}: PASS — {counts[0]} source + {counts[1]} public weekly pages; "
            f"generated dated CSV rows stay in ISO {year}"
        )
    return failures


def main() -> None:
    failures: list[str] = []
    years = requested_years()
    for year in years:
        failures.extend(audit_year(year))
    if failures:
        print("TRUE-YEAR PARAMETERIZATION AUDIT FAILED")
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)
    print(f"True-year parameterization audit PASS for {', '.join(map(str, years))}")


if __name__ == "__main__":
    main()
