#!/usr/bin/env python3
"""Shared ISO-date range utilities for Star Almanack population generators."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, order=True)
class ISOWeek:
    year: int
    week: int

    @property
    def monday(self) -> date:
        return date.fromisocalendar(self.year, self.week, 1)

    @property
    def key(self) -> str:
        return f"{self.year}-W{self.week:02d}"


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Expected ISO date YYYY-MM-DD, got {value!r}") from exc


def weeks_in_range(start: date, end: date, *, max_iso_years: int = 3) -> list[ISOWeek]:
    if end < start:
        raise ValueError("end_date must be on or after start_date")

    weeks: list[ISOWeek] = []
    seen: set[tuple[int, int]] = set()
    day = start
    while day <= end:
        iso = day.isocalendar()
        key = (iso.year, iso.week)
        if key not in seen:
            seen.add(key)
            weeks.append(ISOWeek(*key))
        day += timedelta(days=1)

    years = {week.year for week in weeks}
    if len(years) > max_iso_years:
        labels = ", ".join(map(str, sorted(years)))
        raise ValueError(f"Date range spans {len(years)} ISO years ({labels}); maximum is {max_iso_years}")
    return weeks


def parse_range_args(description: str) -> tuple[date, date, list[ISOWeek]]:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("start_date", type=parse_iso_date, help="inclusive ISO date YYYY-MM-DD")
    parser.add_argument("end_date", type=parse_iso_date, help="inclusive ISO date YYYY-MM-DD")
    args = parser.parse_args()
    try:
        weeks = weeks_in_range(args.start_date, args.end_date)
    except ValueError as exc:
        parser.error(str(exc))
    return args.start_date, args.end_date, weeks


def group_by_year(weeks: list[ISOWeek]) -> dict[int, list[int]]:
    grouped: dict[int, list[int]] = {}
    for item in weeks:
        grouped.setdefault(item.year, []).append(item.week)
    return grouped
