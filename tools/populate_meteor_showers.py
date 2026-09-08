#!/usr/bin/env python3
"""Populate major Almanack meteor-shower maxima for requested years.

This is the generic command-line interface to the established meteor engine.
"""
from __future__ import annotations

import argparse

from populate_2025_2027_meteor_showers import populate_year


def parse_years() -> list[int]:
    parser = argparse.ArgumentParser(description="Populate Star Almanack meteor showers")
    parser.add_argument("years", metavar="YEAR", type=int, nargs="+", help="Years to populate")
    args = parser.parse_args()
    years = list(dict.fromkeys(args.years))
    for year in years:
        if not 1900 <= year <= 2100:
            parser.error(f"YEAR must be between 1900 and 2100: {year}")
    return years


def main() -> None:
    years = parse_years()
    total = sum(populate_year(year) for year in years)
    print(f"Updated {total} meteor-shower page files for: {' '.join(map(str, years))}")


if __name__ == "__main__":
    main()
