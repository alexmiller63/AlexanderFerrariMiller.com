#!/usr/bin/env python3
"""Populate only the ISO weeks intersecting an inclusive date range."""
from __future__ import annotations

from datetime import timedelta

import populate_calendar as calendar
import populate_fixed_sky as fixed_sky
from almanack_sections import require_section
from almanack_calendar import get_event_records
from almanack_paths import week_index
from calendar_fixed_object_ids import patch_file as patch_fixed_object_ids
from calendar_mobile_layout import patch_file as patch_mobile_layout
from iso_date_range import group_by_year, parse_range_args
from planet_finder_layout import patch_file as patch_planet_finder_layout


ASTRONOMY_QUERY_PADDING_DAYS = 45


def populate_selected_year(year: int, selected_weeks: list[int]) -> int:
    first, last = calendar.iso_bounds(year)
    ingresses, phases, wheel = calendar.annual_calendar(year)
    events = calendar.build_events(first, last, ingresses, phases, wheel)

    # Fixed-sky dates are calculated from the same canonical annual sources,
    # then only the requested ISO weeks are written.  Calendar event cells are
    # finally tagged with permanent database IDs for downstream consumers.
    fixed_events = fixed_sky.page_date_map(year)

    changed = 0
    for week in selected_weeks:
        monday = __import__('datetime').date.fromisocalendar(year, week, 1)
        week_dates = {monday + timedelta(days=i) for i in range(7)}
        path = week_index(year, week)
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
            records = get_event_records(text, day)
            if records is None:
                raise RuntimeError(f"Could not find Calendar row {day} in {path}")
            # Keep events structured from read through render.  Permanent identity
            # is metadata, not presentation text, and must never be rediscovered
            # from HTML during normal generation.
            fixed_identities = {fixed_sky._event_identity(value.html) for value in vals}
            for value in vals:
                if value.fixed_object_id is None and value.catalog_target_key is None:
                    raise RuntimeError(
                        f"Canonical fixed-sky event lost semantic identity before Calendar merge "
                        f"for {day}: {fixed_sky._event_identity(value.html)!r}"
                    )
                print(
                    f"CALENDAR-ID-TRACE {day} "
                    f"{fixed_sky._event_identity(value.html)!r} "
                    f"fixed_object_id={value.fixed_object_id} "
                    f"catalog_target_key={value.catalog_target_key}"
                )
            records = [
                event for event in records
                if fixed_sky._event_identity(event.html) not in fixed_identities
            ] + list(vals)
            text, found = fixed_sky.set_events(text, day, records if records else "—")
            if not found:
                raise RuntimeError(f"Could not update Calendar row {day} in {path}")
        path.write_text(text, encoding="utf-8")

        def trace_gamma(stage: str) -> None:
            current = path.read_text(encoding="utf-8")
            marker = "Gam-2"
            pos = current.find(marker)
            if pos >= 0:
                cell_start = current.rfind('<div class="event-cell', 0, pos)
                cell_end = current.find("</div>", pos)
                print(f"CALENDAR-STAGE-TRACE {stage}: {current[cell_start:cell_end + 6]}")

        trace_gamma("after-merge")
        patch_fixed_object_ids(path)
        trace_gamma("after-fixed-object-patch")
        patch_mobile_layout(path)
        trace_gamma("after-mobile-layout")
        patch_planet_finder_layout(path)
        trace_gamma("after-planet-finder-layout")
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
