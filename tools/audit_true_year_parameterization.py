#!/usr/bin/env python3
"""Audit true-year Almanack parameterization and preserved 2026 equivalence.

Two independent guarantees are enforced:
1. requested editions contain dates and ISO-week placement for their own year;
2. the parameterized visibility engine reproduces the preserved canonical 2026
   visibility values exactly, to the stored minute/date/ISO-week precision.

The audit is read-only: canonical 2026 snapshots are never rewritten.
"""
from __future__ import annotations

import csv
import datetime as dt
import re
import sys
from pathlib import Path

import populate_fixed_sky as fixed

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "almanack"
SRC = ROOT / "Star-Almanack-Repo"
SOURCE_SITE = SRC / "site"
GENERATED = SRC / "generated"
DEFAULT_YEARS = (2025, 2027)

DATE_CELL_RE = re.compile(r"<tr><td>([A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}, \d{4})</td>")
ISO_WEEK_RE = re.compile(r"ISO (\d{4})-W(\d{2})")
DATE_COLUMNS = ("best_date", "center_best_date", "date")
CANONICAL_2026 = (
    (SRC / "expanded-bayer-visibility-2026.csv", "ra_h", "best_instant_utc", "best_date", "iso"),
    (SRC / "bright-star-visibility-2026.csv", "ra_h", "best_instant_utc", "best_date", "iso"),
    (SRC / "messier-visibility-2026.csv", "ra_h", "best_instant_utc", "best_date", "iso"),
    (SRC / "constellation-observance-2026.csv", "centroid_ra_h", "best_instant_utc", "best_date", "iso"),
)


def requested_years() -> tuple[int, ...]:
    if len(sys.argv) == 1:
        return DEFAULT_YEARS
    try:
        return tuple(dict.fromkeys(int(x) for x in sys.argv[1:]))
    except ValueError as exc:
        raise SystemExit("Years must be integers, e.g. 2025 2027") from exc


def parse_calendar_date(text: str) -> dt.date:
    return dt.datetime.strptime(text, "%a, %b %d, %Y").date()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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
    rows = read_rows(path)
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


def audit_2026_equivalence() -> list[str]:
    """Recompute canonical 2026 placement without writing any files."""
    failures: list[str] = []
    checked = 0
    for path, ra_column, instant_column, date_column, iso_column in CANONICAL_2026:
        if not path.exists():
            failures.append(f"missing canonical 2026 snapshot: {path}")
            continue
        rows = read_rows(path)
        if not rows:
            failures.append(f"canonical 2026 snapshot is empty: {path}")
            continue
        required = {ra_column, instant_column, date_column, iso_column}
        missing = required - set(rows[0])
        if missing:
            failures.append(f"{path}: missing columns {sorted(missing)}")
            continue

        for n, row in enumerate(rows, start=2):
            instant, day = fixed.best_visibility(float(row[ra_column]), 2026)
            expected = {
                instant_column: instant.strftime("%Y-%m-%d %H:%M"),
                date_column: day.isoformat(),
                iso_column: fixed.iso_label(day),
            }
            for column, value in expected.items():
                actual = (row.get(column) or "").strip()
                if actual != value:
                    failures.append(
                        f"{path}:{n}: 2026 equivalence mismatch in {column}: "
                        f"canonical={actual!r}, parameterized={value!r}"
                    )
            checked += 1

    if not failures:
        print(
            f"2026: EXACT VISIBILITY EQUIVALENCE PASS — {checked} canonical rows "
            "recomputed identically by the parameterized engine"
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

    # This invariant always runs, even when only non-2026 editions are requested.
    failures.extend(audit_2026_equivalence())
    for year in years:
        failures.extend(audit_year(year))

    if failures:
        print("TRUE-YEAR PARAMETERIZATION AUDIT FAILED")
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)
    print(
        f"True-year parameterization audit PASS for {', '.join(map(str, years))}; "
        "canonical 2026 visibility preserved exactly"
    )


if __name__ == "__main__":
    main()
