#!/usr/bin/env python3
"""Year-independent calendar rules shared by Star Almanack editions.

2026 remains the reference edition.  This module extracts rules that must be
identical in every generated year rather than cloning year-specific builders.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

SIGNS = "♈♉♊♋♌♍♎♏♐♑♒♓"
SIGN_NAMES = {
    "♈": "Aries", "♉": "Taurus", "♊": "Gemini", "♋": "Cancer",
    "♌": "Leo", "♍": "Virgo", "♎": "Libra", "♏": "Scorpio",
    "♐": "Sagittarius", "♑": "Capricorn", "♒": "Aquarius", "♓": "Pisces",
}


def iso_week_count(year: int) -> int:
    """Return the number of ISO weeks in *year*."""
    return date(year, 12, 28).isocalendar().week


def zodiac_for_day(d: date, ingresses: Iterable[tuple[datetime, str]]) -> tuple[str, int]:
    """Return tropical zodiac sign and calendrical Zodiac Day for civil date *d*.

    Zodiac Day 1 is the civil date of solar ingress.  Counting continues by
    civil date until the next ingress.  Callers must provide the immediately
    preceding ingress as well as the ingresses spanning the requested dates.
    """
    boundaries = sorted((ts.date(), sign) for ts, sign in ingresses)
    eligible = [(day, sign) for day, sign in boundaries if day <= d]
    if not eligible:
        raise ValueError(f"No solar ingress at or before {d}; include the preceding ingress")
    ingress_day, sign = eligible[-1]
    return sign, (d - ingress_day).days + 1


def zodiac_day_label(d: date, ingresses: Iterable[tuple[datetime, str]]) -> str:
    """Render the established Almanack Zodiac Day notation."""
    sign, day_number = zodiac_for_day(d, ingresses)
    if day_number == 1:
        return f"{sign} ({SIGN_NAMES[sign]}) 1"
    return f"{sign} {day_number}"


def events_label(events: Iterable[str]) -> str:
    """Render multiple same-day calendar events without changing their order."""
    values = [event for event in events if event]
    return "<br>".join(values) if values else "—"
