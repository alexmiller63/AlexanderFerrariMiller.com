#!/usr/bin/env python3
"""Shared semantic object model and reader-facing rendering for the Star Almanack.

Astronomical/source data owns identity, type, magnitude data, provenance, and the
semantic observing aid.  Derived astronomy (declination band and season) is
computed centrally.  Renderers map semantic values to reader-facing notation;
source records never store HTML/SVG markup.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum

from star_almanack_astronomy import declination_band, season_for


class ObservingAid(str, Enum):
    NAKED_EYE = "naked_eye"
    BINOCULARS = "binoculars"
    TELESCOPE = "telescope"


TEXT_AID = {
    ObservingAid.NAKED_EYE: "👁",
    ObservingAid.BINOCULARS: "B",
    ObservingAid.TELESCOPE: "🔭",
}

# HTML observing aids have exactly one source of presentation: the shared
# .visibility-glyph CSS.  Do not put per-renderer dimensions or alignment here.
HTML_AID = {
    ObservingAid.NAKED_EYE: '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/eye.svg" alt="Naked eye" aria-label="Naked eye">',
    ObservingAid.BINOCULARS: '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/binoculars.svg" alt="Binoculars" aria-label="Binoculars">',
    ObservingAid.TELESCOPE: '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/telescope.svg" alt="Telescope" aria-label="Telescope">',
}


def observing_aid_for_magnitude(value: str) -> ObservingAid | None:
    """Derive the established urban-observer baseline for catalog stars.

    This returns semantic data, never a display glyph.  Explicit source-provided
    observing-aid values should be preferred whenever they exist.
    """
    try:
        mag = float((value or "").strip())
    except ValueError:
        return None
    if mag <= 3.5:
        return ObservingAid.NAKED_EYE
    if mag <= 7.5:
        return ObservingAid.BINOCULARS
    return ObservingAid.TELESCOPE


def whole_magnitude(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        rounded = Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return value
    return str(int(rounded))


@dataclass(frozen=True)
class AlmanackObject:
    label: str
    object_type: str
    dec_deg: str
    best_date: date
    observing_aid: ObservingAid | None = None
    magnitude: str = ""
    magnitude_display: str = "none"  # none | whole | literal
    catalog_id: str = ""
    provenance: str = ""

    @property
    def band(self) -> str:
        return declination_band(self.dec_deg)

    @property
    def season(self) -> str:
        return season_for(self.best_date)


def visibility_text(record: AlmanackObject) -> str:
    if record.observing_aid is None:
        return ""
    parts = [TEXT_AID[record.observing_aid]]
    if record.magnitude_display == "whole" and record.magnitude:
        parts.append(f"V {whole_magnitude(record.magnitude)}")
    elif record.magnitude_display == "literal" and record.magnitude:
        parts.append(record.magnitude)
    return " ".join(parts)


def visibility_html(record: AlmanackObject) -> str:
    if record.observing_aid is None:
        return ""
    parts = [HTML_AID[record.observing_aid]]
    if record.magnitude_display == "whole" and record.magnitude:
        parts.append(f"V {whole_magnitude(record.magnitude)}")
    elif record.magnitude_display == "literal" and record.magnitude:
        parts.append(record.magnitude)
    return " ".join(parts)


def classification_text(record: AlmanackObject) -> str:
    return f"{record.band} {record.season}"


def render_text(record: AlmanackObject) -> str:
    parts = [record.label]
    visibility = visibility_text(record)
    if visibility:
        parts.append(visibility)
    parts.append(classification_text(record))
    return " — ".join(parts)


def render_html(record: AlmanackObject) -> str:
    parts = [record.label]
    visibility = visibility_html(record)
    if visibility:
        parts.append(f'<span class="visibility-magnitude">{visibility}</span>')
    parts.append(classification_text(record))
    return " — ".join(parts)
