#!/usr/bin/env python3
"""Verify generated constellation-center occurrences survive final generation.

The audit uses the same machine-readable calendar contract as the generators.
It never infers event identity from where text happens to appear in rendered
HTML.  In particular, an event is valid whether it is the first item in an
Events cell or follows another item after ``<br>``.

Constellation centers recur once per astronomical Aries-to-Aries cycle. ISO
week-numbering years are not astronomical cycles: a given identity can appear
zero, one, or twice in an ISO year near the year boundary. The audit therefore
compares final output with the generated occurrence snapshot.
"""
from __future__ import annotations

import csv
import datetime as dt
import sys
from collections import Counter
from pathlib import Path

from almanack_calendar import ensure_calendar_metadata, get_events

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
ROOTS = (SRC / "site", ROOT / "almanack")


def requested_years() -> tuple[int, ...]:
    if len(sys.argv) == 1:
        return (2026,)
    try:
        return tuple(dict.fromkeys(int(x) for x in sys.argv[1:]))
    except ValueError as exc:
        raise SystemExit("Years must be integers") from exc


def expected_rows(year: int) -> list[dict[str, str]]:
    path = SRC / "generated" / f"constellation-observance-{year}.csv"
    if not path.exists():
        raise SystemExit(f"Missing generated constellation snapshot: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"{year}: generated constellation snapshot is empty")
    identity_counts = Counter(row["name"].strip() for row in rows)
    if any(count not in (1, 2) for count in identity_counts.values()):
        raise SystemExit(f"{year}: unexpected per-identity occurrence count: {identity_counts}")
    return rows


def page_for_date(root: Path, day: dt.date) -> Path:
    iso = day.isocalendar()
    return root / str(iso.year) / f"W{iso.week:02d}" / "index.html"


def actual_counts(root: Path, rows: list[dict[str, str]]) -> Counter[tuple[dt.date, str]]:
    """Count constellation-center events by canonical civil date and identity."""
    result: Counter[tuple[dt.date, str]] = Counter()
    days = sorted({dt.date.fromisoformat(row["center_best_date"]) for row in rows})
    for day in days:
        page = page_for_date(root, day)
        if not page.exists():
            continue
        text = ensure_calendar_metadata(page.read_text(encoding="utf-8"), page)
        cell = get_events(text, day)
        if cell in (None, "", "—"):
            continue
        for item in cell.split("<br>"):
            marker = " center — Constellation — "
            if marker not in item:
                continue
            name = item.split(marker, 1)[0].strip()
            if name:
                result[(day, name)] += 1
    return result


def audit_root(root: Path, year: int, rows: list[dict[str, str]]) -> list[str]:
    failures: list[str] = []
    expected: Counter[tuple[dt.date, str]] = Counter(
        (dt.date.fromisoformat(row["center_best_date"]), row["name"].strip())
        for row in rows
    )
    actual = actual_counts(root, rows)

    if sum(actual.values()) != sum(expected.values()):
        failures.append(
            f"{root}/{year}: expected {sum(expected.values())} constellation-center occurrences, "
            f"found {sum(actual.values())}"
        )

    for key in sorted(set(expected) | set(actual), key=lambda x: (x[0], x[1])):
        if actual[key] != expected[key]:
            day, name = key
            failures.append(
                f"{root}/{year}: {name} center on {day} occurs {actual[key]} times; "
                f"expected {expected[key]}"
            )
    return failures


def main() -> None:
    failures: list[str] = []
    for year in requested_years():
        rows = expected_rows(year)
        year_failures: list[str] = []
        for root in ROOTS:
            year_failures.extend(audit_root(root, year, rows))
        failures.extend(year_failures)
        if not year_failures:
            identities = {row["name"].strip() for row in rows}
            print(
                f"{year}: PASS — {len(rows)} generated constellation-center "
                f"occurrence(s) across {len(identities)} represented identities survive in "
                "source and public output"
            )
    if failures:
        print("CONSTELLATION-CENTER SURVIVAL REGRESSION FAILED")
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
