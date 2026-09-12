#!/usr/bin/env python3
"""Audit the Star Almanack machine-readable calendar contract.

The weekly page path is authoritative for civil-date identity.  Displayed civil
and zodiac text are presentation and must never be required to locate a row.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from almanack_calendar import CALENDAR_RE, ROW_RE, civil_date_text, page_dates

ROOT = Path(__file__).resolve().parents[1]
ROOTS = (ROOT / "Star-Almanack-Repo" / "site", ROOT / "almanack")
SIGNS = {
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
}


def attr(attrs: str, name: str) -> str | None:
    m = re.search(rf'\s+{re.escape(name)}="([^"]*)"', attrs)
    return m.group(1) if m else None


def parse_years() -> list[int]:
    parser = argparse.ArgumentParser(description="Audit Almanack calendar machine-readable keys")
    parser.add_argument("years", metavar="YEAR", type=int, nargs="+")
    args = parser.parse_args()
    return list(dict.fromkeys(args.years))


def audit_page(page: Path) -> list[str]:
    failures: list[str] = []
    text = page.read_text(encoding="utf-8")
    table = CALENDAR_RE.search(text)
    if not table:
        return [f"{page}: missing calendar table"]
    rows = list(ROW_RE.finditer(table.group("body")))
    expected_dates = page_dates(page)
    if len(rows) != 7:
        return [f"{page}: expected 7 calendar rows, found {len(rows)}"]
    for row, day in zip(rows, expected_dates):
        iso = day.isoformat()
        if attr(row.group("trattrs"), "data-date") != iso:
            failures.append(f"{page}: row key for {iso} is missing or wrong")
        if attr(row.group("dateattrs"), "data-date") != iso:
            failures.append(f"{page}: civil-date cell key for {iso} is missing or wrong")
        if row.group("date") != civil_date_text(day):
            failures.append(f"{page}: civil-date display for {iso} is not canonical unpadded form")
        sign = attr(row.group("zattrs"), "data-zodiac-sign")
        zodiac_day = attr(row.group("zattrs"), "data-zodiac-day")
        if sign not in SIGNS:
            failures.append(f"{page}: {iso} has invalid/missing zodiac sign metadata {sign!r}")
        if not zodiac_day or not zodiac_day.isdigit() or int(zodiac_day) < 1:
            failures.append(f"{page}: {iso} has invalid/missing zodiac day metadata {zodiac_day!r}")
    return failures


def main() -> None:
    failures: list[str] = []
    for year in parse_years():
        count = 0
        for root in ROOTS:
            pages = sorted((root / str(year)).glob("W??/index.html"))
            if not pages:
                failures.append(f"{root}/{year}: no weekly pages")
                continue
            for page in pages:
                failures.extend(audit_page(page))
                count += 1
        if not any(f"/{year}" in failure for failure in failures):
            print(f"{year}: calendar contract PASS across {count} source/public weekly pages")
    if failures:
        print("CALENDAR CONTRACT FAILED")
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
