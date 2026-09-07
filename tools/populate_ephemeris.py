#!/usr/bin/env python3
"""Year-parameterized entry point for weekly Solar-System ephemerides."""
from __future__ import annotations

import argparse

from populate_2025_2027_ephemeris import update_year


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate weekly Solar-System ephemeris for one or more ISO years.")
    parser.add_argument("years", nargs="+", type=int, help="ISO week-years to populate")
    args = parser.parse_args()
    total = 0
    for year in args.years:
        changed = update_year(year)
        print(f"Updated {changed} weekly pages for {year}")
        total += changed
    print(f"Updated {total} weekly pages total")


if __name__ == "__main__":
    main()
