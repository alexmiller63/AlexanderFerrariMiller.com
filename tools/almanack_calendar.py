#!/usr/bin/env python3
"""Canonical calendar-row interface for Star Almanack generators.

Rendered civil dates and zodiac labels are presentation only. Generator stages
must address calendar rows by the machine-readable ISO civil date stored in
``data-date`` and must never parse or compare displayed date/zodiac text.

Each solar date owns exactly one calendar row and exactly one zodiac-day cell.
The Events region owns zero or more independent visual event cells. Existing
population stages may continue to exchange events as ``<br>``-separated HTML;
this module translates that legacy interchange format to/from the canonical
multi-cell rendering so the rule is enforced in one place.

The authoritative civil dates of a weekly page are derived from its ISO
``YEAR/Www`` path. This lets us repair/normalize old pages without trusting
whatever date formatting happens to be visible in the HTML.
"""
from __future__ import annotations

import datetime as dt
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

CALENDAR_RE = re.compile(
    r'(?P<head><table\b[^>]*class="[^"]*\bcalendar\b[^"]*"[^>]*>.*?<tbody>)'
    r'(?P<body>.*?)'
    r'(?P<tail></tbody>.*?</table>)',
    re.DOTALL,
)
ROW_RE = re.compile(
    r'<tr(?P<trattrs>[^>]*)>'
    r'<td(?P<dateattrs>[^>]*)>(?P<date>.*?)</td>'
    r'<td(?P<zattrs>[^>]*)>(?P<zodiac>.*?)</td>'
    r'<td(?P<eattrs>[^>]*)>(?P<events>.*?)</td>'
    r'</tr>',
    re.DOTALL,
)
CIVIL_RANGE_RE = re.compile(
    r'(<p><strong>Civil dates:</strong>\s*)(.*?)(</p>)', re.DOTALL
)
EVENT_GRID_RE = re.compile(
    r'^\s*<div\b[^>]*class="[^"]*\bcalendar-events\b[^"]*"[^>]*>(?P<body>.*?)</div>\s*$',
    re.DOTALL,
)
EVENT_CELL_RE = re.compile(
    r'<div\b[^>]*class="[^"]*\bevent-cell\b[^"]*"[^>]*>(?P<event>.*?)</div>',
    re.DOTALL,
)
@dataclass(frozen=True)
class CalendarEvent:
    """Semantic Calendar event; metadata exists before HTML rendering."""
    html: str
    fixed_object_id: int | None = None
    observing_aid: str | None = None


EVENT_STYLE_ID = "calendar-event-cells-css"
EVENT_STYLE = f'''<style id="{EVENT_STYLE_ID}">
.calendar td.calendar-events-region{{padding:.45rem;vertical-align:stretch}}
.calendar-events{{display:grid;grid-template-columns:repeat(auto-fit,minmax(10rem,1fr));gap:.35rem;width:100%;align-items:stretch}}
.calendar-events .event-cell{{min-width:0;padding:.52rem .6rem;border:1px solid var(--rule);border-radius:.35rem;background:var(--paper);line-height:1.45;overflow-wrap:anywhere}}
.calendar-events:empty{{min-height:1.8rem}}
@media(max-width:760px){{.calendar-events{{grid-template-columns:1fr}}}}
</style>'''


def _set_attr(attrs: str, name: str, value: str) -> str:
    value = html.escape(str(value), quote=True)
    pat = re.compile(rf'\s+{re.escape(name)}="[^"]*"')
    replacement = f' {name}="{value}"'
    if pat.search(attrs):
        return pat.sub(replacement, attrs, count=1)
    return attrs + replacement


def _get_attr(attrs: str, name: str) -> str | None:
    m = re.search(rf'\s+{re.escape(name)}="([^"]*)"', attrs)
    return html.unescape(m.group(1)) if m else None


def _ensure_class(attrs: str, class_name: str) -> str:
    m = re.search(r'\s+class="([^"]*)"', attrs)
    if not m:
        return attrs + f' class="{class_name}"'
    classes = m.group(1).split()
    if class_name not in classes:
        classes.append(class_name)
    return attrs[:m.start(1)] + " ".join(classes) + attrs[m.end(1):]


def _event_items(events_html: str) -> list[str]:
    """Return canonical event items from either old or new event markup."""
    raw = events_html.strip()
    grid = EVENT_GRID_RE.match(raw)
    if grid:
        return [m.group("event").strip() for m in EVENT_CELL_RE.finditer(grid.group("body")) if m.group("event").strip()]
    if not raw or raw == "—":
        return []
    return [item.strip() for item in re.split(r'<br\s*/?>', raw, flags=re.IGNORECASE) if item.strip() and item.strip() != "—"]


def _render_event(event: CalendarEvent) -> str:
    attrs = ['class="event-cell"']
    if event.fixed_object_id is not None:
        attrs.append(f'data-fixed-object-id="{int(event.fixed_object_id)}"')
    if event.observing_aid:
        attrs.append(f'data-observing-aid="{html.escape(event.observing_aid, quote=True)}"')
    return f'<div {" ".join(attrs)}>{event.html}</div>'


def _render_event_cells(events: str | list[CalendarEvent]) -> str:
    if isinstance(events, str):
        records = [CalendarEvent(item) for item in _event_items(events)]
    else:
        records = events
    return f'<div class="calendar-events">{"".join(_render_event(event) for event in records)}</div>'


def _legacy_events(events_html: str) -> str:
    """Expose event contents to existing generators without coupling them to layout."""
    items = _event_items(events_html)
    return "<br>".join(items) if items else "—"


def _ensure_event_style(text: str) -> str:
    if f'id="{EVENT_STYLE_ID}"' in text:
        return text
    pos = text.lower().find("</head>")
    if pos < 0:
        return text
    return text[:pos] + EVENT_STYLE + "\n" + text[pos:]


def page_iso_week(path: Path) -> tuple[int, int]:
    """Return the ISO year/week for root and typed Almanack pages."""
    for parent in path.parents:
        if not re.fullmatch(r'W\d{2}', parent.name):
            continue
        year_name = parent.parent.name
        if not re.fullmatch(r'\d{4}', year_name):
            continue
        year, week = int(year_name), int(parent.name[1:])
        dt.date.fromisocalendar(year, week, 1)
        return year, week
    raise ValueError(f"Weekly Almanack page is not under YEAR/Www: {path}")

def page_dates(path: Path) -> list[dt.date]:
    year, week = page_iso_week(path)
    monday = dt.date.fromisocalendar(year, week, 1)
    return [monday + dt.timedelta(days=i) for i in range(7)]


def civil_date_text(day: dt.date) -> str:
    return f"{day:%a, %b} {day.day}, {day.year}"


def civil_range_text(first: dt.date, last: dt.date) -> str:
    return f"{first:%b} {first.day}, {first.year} – {last:%b} {last.day}, {last.year}"


def _render_row(parts: dict[str, str]) -> str:
    return (
        f'<tr{parts["trattrs"]}>'
        f'<td{parts["dateattrs"]}>{parts["date"]}</td>'
        f'<td{parts["zattrs"]}>{parts["zodiac"]}</td>'
        f'<td{parts["eattrs"]}>{parts["events"]}</td>'
        '</tr>'
    )


def ensure_calendar_metadata(text: str, path: Path) -> str:
    """Normalize one weekly page and install stable machine-readable keys."""
    match = CALENDAR_RE.search(text)
    if not match:
        raise ValueError(f"No calendar table found in {path}")
    rows = list(ROW_RE.finditer(match.group("body")))
    if len(rows) != 7:
        raise ValueError(f"Expected 7 calendar rows in {path}, found {len(rows)}")

    dates = page_dates(path)
    body = match.group("body")
    out: list[str] = []
    cursor = 0
    for row_match, day in zip(rows, dates):
        out.append(body[cursor:row_match.start()])
        parts = row_match.groupdict()
        iso = day.isoformat()
        parts["trattrs"] = _set_attr(parts["trattrs"], "data-date", iso)
        parts["dateattrs"] = _set_attr(parts["dateattrs"], "data-date", iso)
        parts["date"] = civil_date_text(day)
        if _get_attr(parts["zattrs"], "data-zodiac-sign") is None:
            parts["zattrs"] = _set_attr(parts["zattrs"], "data-zodiac-sign", "")
        if _get_attr(parts["zattrs"], "data-zodiac-day") is None:
            parts["zattrs"] = _set_attr(parts["zattrs"], "data-zodiac-day", "")
        parts["eattrs"] = _ensure_class(parts["eattrs"], "calendar-events-region")
        parts["events"] = _render_event_cells(parts["events"])
        out.append(_render_row(parts))
        cursor = row_match.end()
    out.append(body[cursor:])
    new_body = "".join(out)
    text = text[:match.start("body")] + new_body + text[match.end("body"):]

    first, last = dates[0], dates[-1]
    text = CIVIL_RANGE_RE.sub(
        lambda m: m.group(1) + civil_range_text(first, last) + m.group(3),
        text,
        count=1,
    )
    return _ensure_event_style(text)


def _transform_row(text: str, day: dt.date, transform: Callable[[dict[str, str]], None]) -> tuple[str, bool]:
    iso = day.isoformat()
    match = CALENDAR_RE.search(text)
    if not match:
        return text, False
    body = match.group("body")
    for row_match in ROW_RE.finditer(body):
        parts = row_match.groupdict()
        if _get_attr(parts["trattrs"], "data-date") != iso:
            continue
        transform(parts)
        replacement = _render_row(parts)
        new_body = body[:row_match.start()] + replacement + body[row_match.end():]
        return text[:match.start("body")] + new_body + text[match.end("body"):], True
    return text, False


def get_events(text: str, day: dt.date) -> str | None:
    iso = day.isoformat()
    match = CALENDAR_RE.search(text)
    if not match:
        return None
    for row_match in ROW_RE.finditer(match.group("body")):
        if _get_attr(row_match.group("trattrs"), "data-date") == iso:
            return _legacy_events(row_match.group("events"))
    return None


def set_events(text: str, day: dt.date, events_html: str | list[CalendarEvent]) -> tuple[str, bool]:
    def transform(parts: dict[str, str]) -> None:
        parts["eattrs"] = _ensure_class(parts["eattrs"], "calendar-events-region")
        parts["events"] = _render_event_cells(events_html)
    updated, found = _transform_row(text, day, transform)
    return (_ensure_event_style(updated) if found else updated), found


def clear_events(text: str) -> str:
    match = CALENDAR_RE.search(text)
    if not match:
        return text
    body = match.group("body")
    out: list[str] = []
    cursor = 0
    for row_match in ROW_RE.finditer(body):
        out.append(body[cursor:row_match.start()])
        parts = row_match.groupdict()
        parts["eattrs"] = _ensure_class(parts["eattrs"], "calendar-events-region")
        parts["events"] = _render_event_cells("")
        out.append(_render_row(parts))
        cursor = row_match.end()
    out.append(body[cursor:])
    new_body = "".join(out)
    text = text[:match.start("body")] + new_body + text[match.end("body"):]
    return _ensure_event_style(text)


def set_zodiac(
    text: str,
    day: dt.date,
    *,
    sign_name: str,
    zodiac_day: int,
    rendered_html: str,
) -> tuple[str, bool]:
    def transform(parts: dict[str, str]) -> None:
        parts["zattrs"] = _set_attr(parts["zattrs"], "data-zodiac-sign", sign_name)
        parts["zattrs"] = _set_attr(parts["zattrs"], "data-zodiac-day", str(zodiac_day))
        parts["zodiac"] = rendered_html
    return _transform_row(text, day, transform)


def has_date(text: str, day: dt.date) -> bool:
    return get_events(text, day) is not None
