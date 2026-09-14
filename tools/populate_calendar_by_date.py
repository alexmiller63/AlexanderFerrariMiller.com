#!/usr/bin/env python3
"""Populate only the ISO weeks intersecting an inclusive date range."""
from __future__ import annotations

from datetime import timedelta

import populate_calendar as calendar
from calendar_mobile_layout import patch_file as patch_mobile_layout
from iso_date_range import group_by_year, parse_range_args


def populate_selected_year(year: int, selected_weeks: list[int]) -> int:
    first, last = calendar.iso_bounds(year)
    query_start, query_stop = first - timedelta(days=45), last + timedelta(days=45)

    print(f"Calculating {year} Sun and Moon calendar astronomy from cached SPK source data")
    sun = calendar.source_longitudes("sun", query_start, query_stop)
    moon = calendar.source_longitudes("moon", query_start, query_stop)
    ingresses = calendar.solar_ingresses(sun)
    wheel = calendar.wheel_of_year(sun)
    phases = calendar.lunar_phases(sun, moon)
    events = calendar.build_events(first, last, ingresses, phases, wheel)

    changed = 0
    for week in selected_weeks:
        for base in (calendar.SOURCE_ROOT, calendar.PUBLIC_ROOT):
            path = base / str(year) / f"W{week:02d}" / "index.html"
            if not path.exists():
                raise RuntimeError(f"Missing weekly page: {path.relative_to(calendar.ROOT)}")
            page_changed = calendar.patch_page(path, ingresses, events)
            layout_changed = patch_mobile_layout(path)
            if page_changed or layout_changed:
                changed += 1
    return changed


def main() -> None:
    start, end, weeks = parse_range_args("Populate Star Almanack Calendar by inclusive ISO date range")
    grouped = group_by_year(weeks)
    total = 0
    for year, selected in grouped.items():
        changed = populate_selected_year(year, selected)
        total += changed
        labels = " ".join(f"W{week:02d}" for week in selected)
        print(f"{year}: updated {changed} Calendar page copies for {labels}")
    print(f"Calendar population complete for {start.isoformat()} through {end.isoformat()}: {total} page copies updated")


if __name__ == "__main__":
    main()