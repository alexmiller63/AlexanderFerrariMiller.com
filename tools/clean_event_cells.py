#!/usr/bin/env python3
"""Normalize Almanack calendar structure and clear generated Events cells."""
from __future__ import annotations

import argparse
from pathlib import Path

from almanack_calendar import clear_events, ensure_calendar_metadata

ROOT = Path(__file__).resolve().parents[1]
BASES = (ROOT / "Star-Almanack-Repo" / "site", ROOT / "almanack")


def parse_years() -> list[int]:
    parser = argparse.ArgumentParser(description="Normalize and clear generated Star Almanack event cells")
    parser.add_argument("years", metavar="YEAR", type=int, nargs="+", help="Years to clear")
    args = parser.parse_args()
    years = list(dict.fromkeys(args.years))
    for year in years:
        if not 1900 <= year <= 2100:
            parser.error(f"YEAR must be between 1900 and 2100: {year}")
    return years


def clear_year(year: int) -> int:
    changed = 0
    for base in BASES:
        # Only canonical ISO-week directories (W01..W53) participate in the
        # production calendar contract.  Test/sandbox directories such as
        # W22-glyph-test are deliberately excluded.
        for page in sorted((base / str(year)).glob("W??/index.html")):
            text = page.read_text(encoding="utf-8")
            new = ensure_calendar_metadata(text, page)
            new = clear_events(new)
            if new != text:
                page.write_text(new, encoding="utf-8")
                changed += 1
    print(f"{year}: normalized calendar metadata/date display and cleared {changed} page files")
    return changed


def main() -> None:
    years = parse_years()
    total = sum(clear_year(year) for year in years)
    print(f"Normalized and cleared {total} page files for: {' '.join(map(str, years))}")


if __name__ == "__main__":
    main()
