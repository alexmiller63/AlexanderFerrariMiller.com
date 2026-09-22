#!/usr/bin/env python3
"""Populate only the ISO weeks intersecting an inclusive date range."""
from __future__ import annotations

from datetime import timedelta

import populate_calendar as calendar
import populate_fixed_sky as fixed_sky
from almanack_sections import require_section
from almanack_paths import typed_page
from calendar_fixed_object_ids import patch_file as patch_fixed_object_ids
from calendar_mobile_layout import patch_file as patch_mobile_layout
from iso_date_range import group_by_year, parse_range_args
from planet_finder_layout import patch_file as patch_planet_finder_layout


ASTRONOMY_QUERY_PADDING_DAYS = 45


def populate_selected_year(year: int, selected_weeks: list[int]) -> int:
    first, last = calendar.iso_bounds(year)
    query_start, query_stop = first - timedelta(days=ASTRONOMY_QUERY_PADDING_DAYS), last + timedelta(days=ASTRONOMY_QUERY_PADDING_DAYS)

    print(f"Calculating {year} Sun and Moon calendar astronomy from cached SPK source data")
    sun = calendar.source_longitudes("sun", query_start, query_stop)
    moon = calendar.source_longitudes("moon", query_start, query_stop)
    ingresses = calendar.solar_ingresses(sun)
    wheel = calendar.wheel_of_year(sun)
    phases = calendar.lunar_phases(sun, moon)
    events = calendar.build_events(first, last, ingresses, phases, wheel)

    # Fixed-sky dates are calculated from the same canonical annual sources,
    # then only the requested ISO weeks are written.  Calendar event cells are
    # finally tagged with permanent database IDs for downstream consumers.
    fixed_events = fixed_sky.page_date_map(year)

    changed = 0
    for week in selected_weeks:
        monday = __import__('datetime').date.fromisocalendar(year, week, 1)
        week_dates = {monday + timedelta(days=i) for i in range(7)}
        path = typed_page(year, week, "calendar")
        if not path.exists():
            raise RuntimeError(f"Missing weekly page: {path.relative_to(calendar.ROOT)}")
        before = path.read_text(encoding="utf-8")
        require_section(before, 2, path)
        calendar.patch_page(path, ingresses, events)

        # Merge canonical fixed-sky events without touching other event types.
        text = path.read_text(encoding="utf-8")
        text = fixed_sky.ensure_calendar_metadata(text, path)
        for day in week_dates:
            vals = fixed_events.get(day, [])
            if not vals:
                continue
            cell = fixed_sky.get_events(text, day)
            if cell is None:
                raise RuntimeError(f"Could not find Calendar row {day} in {path}")
            keep = [] if cell == "—" else [x for x in cell.split("<br>") if x]
            for value in vals:
                base_label = value.html.split(" — ", 1)[0]
                keep = [
                    x for x in keep
                    if not (
                        (x.html if isinstance(x, fixed_sky.CalendarEvent) else x) == base_label
                        or (x.html if isinstance(x, fixed_sky.CalendarEvent) else x).startswith(base_label + " — ")
                    )
                ]
                keep.append(value)
            records = [fixed_sky.CalendarEvent(x) for x in keep if isinstance(x, str)] + [x for x in keep if isinstance(x, fixed_sky.CalendarEvent)]
            text, found = fixed_sky.set_events(text, day, records if records else "—")
            if not found:
                raise RuntimeError(f"Could not update Calendar row {day} in {path}")
        path.write_text(text, encoding="utf-8")
        patch_fixed_object_ids(path)
        patch_mobile_layout(path)
        patch_planet_finder_layout(path)
        if path.read_text(encoding="utf-8") != before:
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
