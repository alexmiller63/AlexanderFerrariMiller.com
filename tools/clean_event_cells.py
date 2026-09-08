#!/usr/bin/env python3
"""Clear Almanack calendar Events cells for one or more requested years."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASES = (ROOT / "Star-Almanack-Repo" / "site", ROOT / "almanack")


def parse_years() -> list[int]:
    parser = argparse.ArgumentParser(description="Clear generated Star Almanack event cells")
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
        for page in (base / str(year)).glob("W*/index.html"):
            text = page.read_text(encoding="utf-8")
            new = re.sub(r'(<tr><td>.*?</td><td>.*?</td><td>).*?(</td></tr>)', r'\1—\2', text)
            if new != text:
                page.write_text(new, encoding="utf-8")
                changed += 1
    print(f"{year}: cleared {changed} calendar page files")
    return changed


def main() -> None:
    years = parse_years()
    total = sum(clear_year(year) for year in years)
    print(f"Cleared {total} page files for: {' '.join(map(str, years))}")


if __name__ == "__main__":
    main()
