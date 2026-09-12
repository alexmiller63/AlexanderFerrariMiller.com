#!/usr/bin/env python3
"""Audit true-year Almanack parameterization and preserved 2026 equivalence.

Two independent guarantees are enforced:
1. requested weekly editions contain dates and ISO-week placement for their own ISO year;
2. parameterized visibility reproduces the preserved canonical 2026 values exactly.

Weekly-page identity is read only from machine metadata (data-date) and the
YEAR/Www container. Rendered civil dates and zodiac labels are presentation and
are deliberately ignored by this audit.

Generated visibility tables are keyed to the requested ISO edition year. A
physical phase is calculated in neighboring Aries-to-Aries cycles and retained
only when its rounded civil date belongs to the requested ISO week-numbering
year. Thus Dec/Jan boundary dates are legitimate when their ISO year matches
the requested edition.

The audit is read-only: canonical 2026 snapshots are never rewritten.
"""
from __future__ import annotations

import csv
import datetime as dt
import re
import sys
from pathlib import Path

import populate_fixed_sky as fixed
from almanack_calendar import CALENDAR_RE, ROW_RE, _get_attr, page_dates

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "almanack"
SRC = ROOT / "Star-Almanack-Repo"
SOURCE_SITE = SRC / "site"
GENERATED = SRC / "generated"
DEFAULT_YEARS = (2025, 2027)

PAGE_TITLE_RES = (
    re.compile(r"<title>ISO (\d{4})-W(\d{2}) · Star Almanack</title>"),
    re.compile(r"<title>ISO week (\d{2}) (\d{4}) · Star Almanack</title>"),
)
DATE_COLUMNS = ("best_date", "center_best_date", "date")


def requested_years() -> tuple[int, ...]:
    if len(sys.argv) == 1:
        return DEFAULT_YEARS
    try:
        return tuple(dict.fromkeys(int(x) for x in sys.argv[1:]))
    except ValueError as exc:
        raise SystemExit("Years must be integers, e.g. 2025 2027") from exc


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def page_title_iso(text: str) -> tuple[int, int] | None:
    match = PAGE_TITLE_RES[0].search(text)
    if match:
        year, week = map(int, match.groups())
        return year, week
    match = PAGE_TITLE_RES[1].search(text)
    if match:
        week, year = map(int, match.groups())
        return year, week
    return None


def audit_week_pages(root: Path, year: int) -> tuple[int, list[str]]:
    pages = sorted((root / str(year)).glob("W??/index.html"))
    failures: list[str] = []
    if not pages:
        return 0, [f"no weekly pages under {root / str(year)}"]

    for page in pages:
        week = int(page.parent.name[1:])
        text = page.read_text(encoding="utf-8")

        title_iso = page_title_iso(text)
        if title_iso is None:
            failures.append(f"{page}: missing recognized ISO page title")
        elif title_iso != (year, week):
            title_year, title_week = title_iso
            failures.append(
                f"{page}: page title is ISO {title_year}-W{title_week:02d}, "
                f"expected ISO {year}-W{week:02d}"
            )

        table = CALENDAR_RE.search(text)
        if not table:
            failures.append(f"{page}: no calendar table found")
            continue
        rows = list(ROW_RE.finditer(table.group("body")))
        expected = page_dates(page)
        if len(rows) != 7:
            failures.append(f"{page}: expected 7 calendar rows, found {len(rows)}")
            continue
        for row, day in zip(rows, expected):
            actual = _get_attr(row.group("trattrs"), "data-date")
            if actual != day.isoformat():
                failures.append(
                    f"{page}: row machine date {actual!r}, expected {day.isoformat()}"
                )
            iso = day.isocalendar()
            if iso.year != year or iso.week != week:
                failures.append(
                    f"{page}: derived date {day.isoformat()} belongs to ISO "
                    f"{iso.year}-W{iso.week:02d}, not ISO {year}-W{week:02d}"
                )
    return len(pages), failures


def audit_generated_csv(path: Path, iso_year: int) -> list[str]:
    failures: list[str] = []
    rows = read_rows(path)
    if not rows:
        return [f"{path}: generated CSV is empty"]

    date_column = next((name for name in DATE_COLUMNS if name in rows[0]), None)
    if date_column is None:
        return failures

    first = dt.date.fromisocalendar(iso_year, 1, 1)
    weeks = dt.date(iso_year, 12, 28).isocalendar().week
    last = dt.date.fromisocalendar(iso_year, weeks, 7)
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
        if not first <= day <= last or day.isocalendar().year != iso_year:
            failures.append(
                f"{path}:{n}: {date_column} {day.isoformat()} does not belong to ISO "
                f"{iso_year} ({first.isoformat()} through {last.isoformat()})"
            )
        if iso_column:
            expected_iso = fixed.iso_label(day)
            actual_iso = (row.get(iso_column) or "").strip()
            if actual_iso and actual_iso != expected_iso:
                failures.append(
                    f"{path}:{n}: {iso_column}={actual_iso!r} does not match date "
                    f"{day.isoformat()} ({expected_iso})"
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


def canonical_occurrence(occurrences: list[tuple[dt.datetime, dt.date]], row: dict[str, str]) -> tuple[dt.datetime, dt.date] | None:
    """Select the ISO-year occurrence corresponding to a canonical snapshot row."""
    canonical_day = dt.date.fromisoformat(row["best_date"][:10])
    matches = [(instant, day) for instant, day in occurrences if day == canonical_day]
    if len(matches) == 1:
        return matches[0]
    return None


def audit_2026_equivalence() -> list[str]:
    """Recompute canonical 2026 placement without writing files."""
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
        for n, row in enumerate(rows, start=2):
            occurrences = fixed.best_visibility_occurrences_for_iso_year(float(row[ra_column]), 2026)
            selected = canonical_occurrence(occurrences, row)
            if selected is None:
                failures.append(
                    f"{path}:{n}: no unique parameterized 2026 occurrence for canonical "
                    f"{date_column}={row[date_column]!r}"
                )
                continue
            instant, day = selected
            r = dict(row)
            r[instant_column] = instant.strftime("%Y-%m-%d %H:%M")
            r[date_column] = day.isoformat()
            r[iso_column] = fixed.iso_label(day)
            generated.append(r)
        if len(generated) == len(rows):
            failures.extend(compare_rows(path, rows, generated, (instant_column, date_column, iso_column)))
        checked += len(rows)

    messier_path = SRC / "messier-visibility-2026.csv"
    if not messier_path.exists():
        failures.append(f"missing canonical 2026 snapshot: {messier_path}")
    else:
        rows = read_rows(messier_path)
        generated = []
        for n, row in enumerate(rows, start=2):
            canonical = dt.datetime.strptime(row["best_instant_utc"], "%Y-%m-%d %H:%M")
            target = fixed.apparent_sun_ra_hours(canonical)
            occurrences = fixed.solar_ra_occurrences_for_iso_year(target, 2026)
            selected = canonical_occurrence(occurrences, row)
            if selected is None:
                failures.append(
                    f"{messier_path}:{n}: no unique parameterized 2026 occurrence for canonical "
                    f"best_date={row['best_date']!r}"
                )
                continue
            instant, day = selected
            r = dict(row)
            r["best_instant_utc"] = instant.strftime("%Y-%m-%d %H:%M")
            r["best_date"] = day.isoformat()
            r["iso"] = fixed.iso_label(day)
            generated.append(r)
        if len(generated) == len(rows):
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
            f"generated dated CSV rows belong to ISO {year}"
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
