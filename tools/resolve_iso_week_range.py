#!/usr/bin/env python3
"""Resolve the shared four-field generator interface to an inclusive ISO date range.

Usage:
  python tools/resolve_iso_week_range.py START_YEAR START_WEEK [END_YEAR] [END_WEEK]

Start year/week are required. End year/week are optional as a pair. If both
end fields are blank, exactly the starting ISO week is selected.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta


def iso_monday(year: int, week: int) -> date:
    try:
        return date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise SystemExit(f"Invalid ISO week {year}-W{week:02d}: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("start_year", type=int)
    parser.add_argument("start_week", type=int)
    parser.add_argument("end_year", nargs="?", default="")
    parser.add_argument("end_week", nargs="?", default="")
    args = parser.parse_args()

    end_year = str(args.end_year or "").strip()
    end_week = str(args.end_week or "").strip()
    if bool(end_year) != bool(end_week):
        raise SystemExit("End year and End week must either both be blank or both be supplied")

    start = iso_monday(args.start_year, args.start_week)
    if end_year:
        end_monday = iso_monday(int(end_year), int(end_week))
    else:
        end_monday = start
    if end_monday < start:
        raise SystemExit("End ISO week must not precede Start ISO week")

    end = end_monday + timedelta(days=6)
    print(start.isoformat(), end.isoformat())


if __name__ == "__main__":
    main()
