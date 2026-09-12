#!/usr/bin/env python3
"""Canonical calendar-row interface for Star Almanack generators.

Rendered civil dates and zodiac labels are presentation only.  Generator stages
must address calendar rows by the machine-readable ISO civil date stored in
``data-date`` and must never parse or compare displayed date/zodiac text.

The authoritative civil dates of a weekly page are derived from its ISO
``YEAR/Www`` path.  This lets us repair/normalize old pages without trusting
whatever date formatting happens to be visible in the HTML.
"""
from __future__ import annotations

import datetime as dt
import html
import re
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


def page_iso_week(path: Path) -> tuple[int, int]:
    week_name = path.parent.name
    year_name = path.parent.parent.name
    if not re.fullmatch(r'W\d{2}', week_name) or not re.fullmatch(r'\d{4}', year_name):
        raise ValueError(f"Weekly Almanack page is not under YEAR/Www: {path}")
    year, week = int(year_name), int(week_name[1:])
    # Validation is delegated to fromisocalendar so impossible W53 values fail.
    dt.date.fromisocalendar(year, week, 1)
    return year, week


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
    """Normalize one weekly page and install stable machine-readable keys.

    The 7 civil dates are derived from the ISO week encoded in ``path``.  No
    displayed date or zodiac text is parsed to discover identity.
    """
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
        # Zodiac metadata exists independently of its rendered glyph/wording.
        if _get_attr(parts["zattrs"], "data-zodiac-sign") is None:
            parts["zattrs"] = _set_attr(parts["zattrs"], "data-zodiac-sign", "")
        if _get_attr(parts["zattrs"], "data-zodiac-day") is None:
            parts["zattrs"] = _set_attr(parts["zattrs"], "data-zodiac-day", "")
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
    return text


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
            return row_match.group("events")
    return None


def set_events(text: str, day: dt.date, events_html: str) -> tuple[str, bool]:
    def transform(parts: dict[str, str]) -> None:
        parts["events"] = events_html
    return _transform_row(text, day, transform)


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
        parts["events"] = "—"
        out.append(_render_row(parts))
        cursor = row_match.end()
    out.append(body[cursor:])
    new_body = "".join(out)
    return text[:match.start("body")] + new_body + text[match.end("body"):]


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
