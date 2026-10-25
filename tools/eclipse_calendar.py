"""Merge catalog eclipses into canonical Calendar rows without losing other events."""
import html
import re
from datetime import date
from pathlib import Path

from almanack_calendar import CalendarEvent, ensure_calendar_metadata, get_event_records, page_dates, set_events
from eclipse_editorial import format_utc, load_events, title

ROOT = Path(__file__).resolve().parents[1]


def populate_eclipse_calendar(text, path, events=None):
    if events is None:
        if not (ROOT / "generated/eclipse-catalog/eclipses-2025-2036.json").exists():
            return text
        events = load_events(ROOT)
    dates = set(page_dates(path))
    selected = [e for e in events.values() if date.fromisoformat(e["date_utc"]) in dates]
    if not selected:
        return text
    text = ensure_calendar_metadata(text, path)
    for event in selected:
        day = date.fromisoformat(event["date_utc"])
        records = get_event_records(text, day)
        if records is None:
            raise RuntimeError(f"Missing Calendar row {day} in {path}")
        eid = event["id"]
        # Replace this permanent event, or its older untagged Calendar rendering.
        records = [r for r in records if
                   f'data-eclipse-id="{eid}"' not in r.html and not (
                       'data-eclipse-id=' not in r.html and
                       re.search(rf'\b{event["kind"]} eclipse\b', r.html, re.I))]
        kind = html.escape(event["kind"], quote=True)
        label = html.escape(title(event))
        href = "/almanack/" + event["detail_path"].lstrip("/")
        body = (f'<span data-eclipse-id="{html.escape(eid, quote=True)}">'
                f'<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/{kind}-eclipse.svg" '
                f'alt="{kind.capitalize()} eclipse"> '
                f'<a href="{html.escape(href, quote=True)}">{label}</a> · '
                f'greatest eclipse {html.escape(format_utc(event.get("greatest_utc")))}')
        for field, heading in (("magnitude", "magnitude"), ("visibility", "visibility"), ("observing_note", "observing")):
            if event.get(field):
                body += f' · {heading}: {html.escape(str(event[field]))}'
        body += '</span>'
        text, found = set_events(text, day, [CalendarEvent(body)] + records)
        if not found:
            raise RuntimeError(f"Could not write eclipse {eid} in {path}")
    return text
