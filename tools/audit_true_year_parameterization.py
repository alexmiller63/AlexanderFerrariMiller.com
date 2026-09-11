#!/usr/bin/env python3
"""Audit true-year Almanack parameterization and preserved 2026 equivalence.

Two independent guarantees are enforced:
1. requested weekly editions contain dates and ISO-week placement for their own ISO year;
2. parameterized visibility reproduces the preserved canonical 2026 values exactly.

Generated annual visibility tables are civil observing cycles, not ISO-week
containers: the preserved 2026 engine explicitly allows rounded dates from
2026-01-01 through 2027-01-01. Their ISO label must match the date, but the ISO
week-year is allowed to cross the civil-year boundary.

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
PAGE_TITLE_RE = re.compile(r"<title>ISO (\d{4})-W(\d{2}) · Star Almanack</title>")
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

        title_match = PAGE_TITLE_RE.search(text)
        if not title_match:
            failures.append(f"{page}: missing canonical ISO page title")
        else:
            title_year, title_week = map(int, title_match.groups())
            if (title_year, title_week) != (year, week):
                failures.append(
                    f"{page}: page title is ISO {title_year}-W{title_week:02d}, "
                    f"expected ISO {year}-W{week:02d}"
                )

        # Adjacent-year ISO labels are legitimate in prev/next navigation.
        # Calendar rows, however, must all belong to this page's ISO week.
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

    cycle_min = dt.date(year, 1, 1)
    cycle_max = dt.date(year + 1, 1, 1)
    iso_column = next((name for name in ("iso", "center_iso") if name in rows[0]), None)

    for n, row in enumerate(rows, start=2):
        raw = (row.get(date_column) or "").strip()
        if not raw:
            continue
        try:
            day = dt.date.fromisoformat(raw[:10])
        except ValueError:
            failures.append(f"{path}:{n}: invalid {date_column}={raw!r}")
            continue
        if not cycle_min <= day <= cycle_max:
            failures.append(
                f"{path}:{n}: {date_column} {day.isoformat()} escaped the {year} observing cycle "
                f"({cycle_min.isoformat()} through {cycle_max.isoformat()})"
            )
        if iso_column:
            expected_iso = fixed.iso_label(day)
            actual_iso = (row.get(iso_column) or "").strip()
            if actual_iso and actual_iso != expected_iso:
                failures.append(
                    f"{path}:{n}: {iso_column}={actual_iso!r} does not match date {day.isoformat()} "
                    f"({expected_iso})"
                )
    return failures


def compare_rows(path: Path, canonical: list[dict[str, str]], generated: list[dict[str, str]], columns: tuple[str, ...]) -> list[str]:
    failures: list[str] = []
    if len(canonical) != len(generated):
        return [f"{path}: canonical row count {len(canonical)} != parameterized row count {len(generated)}"]
    for n, (old, new) in enumerate(zip(canonical, generated), start=2):
        for column in columns:
            actual = (old.get(column) or "").strip()
            value = (new.get(column) or "").strip()
            if actual != value:
                failures.append(
                    f"{path}:{n}: 2026 equivalence mismatch in {column}: "
                    f"canonical={actual!r}, parameterized={value!r}"
                )
    return failures


def audit_2026_equivalence() -> list[str]:
    """Recompute or re-parameterize canonical 2026 placement without writing files."""
    failures: list[str] = []
    checked = 0

    direct_specs = (
        (SRC / "expanded-bayer-visibility-2026.csv", "ra_h", "best_instant_utc", "best_date", "iso"),
        (SRC / "bright-star-visibility-2026.csv", "ra_h", "best_instant_utc", "best_date", "iso"),
        (SRC / "constellation-observance-2026.csv", "centroid_ra_h", "best_instant_utc", "best_date", "iso"),
    )
    for path, ra_column, instant_column, date_column, iso_column in direct_specs:
        if not path.exists():
            failures.append(f"missing canonical 2026 snapshot: {path}")
            continue
        rows = read_rows(path)
        generated = []
        for row in rows:
            instant, day = fixed.best_visibility(float(row[ra_column]), 2026)
            r = dict(row)
            r[instant_column] = instant.strftime("%Y-%m-%d %H:%M")
            r[date_column] = day.isoformat()
            r[iso_column] = fixed.iso_label(day)
            generated.append(r)
        failures.extend(compare_rows(path, rows, generated, (instant_column, date_column, iso_column)))
        checked += len(rows)

    messier_path = SRC / "messier-visibility-2026.csv"
    if not messier_path.exists():
        failures.append(f"missing canonical 2026 snapshot: {messier_path}")
    else:
        rows = read_rows(messier_path)
        generated = fixed.redated_preserving_2026_phase(rows, 2026)
        failures.extend(compare_rows(messier_path, rows, generated, ("best_instant_utc", "best_date", "iso")))
        checked += len(rows)

    if not failures:
        print(
            f"2026: EXACT VISIBILITY EQUIVALENCE PASS — {checked} canonical rows "
            "preserved exactly by the parameterized paths"
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
            f"generated dated CSV rows remain inside the {year} observing cycle"
        )
    return failures


def main() -> None:
    failures: list[str] = []
    years = requested_years()

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
