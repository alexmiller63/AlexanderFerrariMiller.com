#!/usr/bin/env python3
"""Shared semantic object model and reader-facing rendering for the Star Almanack.

Astronomical/source data owns identity, type, magnitude data, provenance, and the
semantic observing aid.  Derived astronomy (declination band and season) is
computed centrally.  Renderers map semantic values to reader-facing notation;
source records never store HTML/SVG markup.

Variable-star policy is centralized here too.  The normal reader view marks only
stars whose catalogued V-band range spans at least 1.0 magnitude.  The browser's
Variability: All mode may reveal every catalogued variable and shows its range to
one decimal place; generators only provide the underlying semantic values.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from html import escape

from almanack_paths import VISIBILITY_GLYPH_ROOT
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

HTML_AID = {
    ObservingAid.NAKED_EYE: f'<img class="visibility-glyph" src="{VISIBILITY_GLYPH_ROOT}/eye.svg" alt="Naked eye" aria-label="Naked eye">',
    ObservingAid.BINOCULARS: f'<img class="visibility-glyph" src="{VISIBILITY_GLYPH_ROOT}/binoculars.svg" alt="Binoculars" aria-label="Binoculars">',
    ObservingAid.TELESCOPE: f'<img class="visibility-glyph" src="{VISIBILITY_GLYPH_ROOT}/telescope.svg" alt="Telescope" aria-label="Telescope">',
}


def observing_aid_for_magnitude(value: str) -> ObservingAid | None:
    """Derive the established urban-observer baseline for catalog stars."""
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


def one_decimal(value: str) -> str:
    try:
        return str(Decimal((value or "").strip()).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    except InvalidOperation:
        return (value or "").strip()


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
    variability_type: str = ""
    variability_max_v: str = ""
    variability_min_v: str = ""

    @property
    def band(self) -> str:
        return declination_band(self.dec_deg)

    @property
    def season(self) -> str:
        return season_for(self.best_date)

    @property
    def variability_span(self) -> float | None:
        try:
            return abs(float(self.variability_min_v) - float(self.variability_max_v))
        except (TypeError, ValueError):
            return None

    @property
    def significant_variable(self) -> bool:
        span = self.variability_span
        return bool(self.variability_type and span is not None and span >= 1.0)


def visibility_text(record: AlmanackObject) -> str:
    if record.observing_aid is None:
        return ""
    parts = [TEXT_AID[record.observing_aid]]
    if record.significant_variable:
        parts.append("V")
    if record.magnitude_display == "whole" and record.magnitude:
        parts.append(whole_magnitude(record.magnitude))
    elif record.magnitude_display == "literal" and record.magnitude:
        parts.append(record.magnitude)
    return " ".join(parts)


def visibility_html(record: AlmanackObject) -> str:
    if record.observing_aid is None:
        return ""
    parts = [HTML_AID[record.observing_aid]]
    if record.variability_type and record.variability_span is not None:
        hidden = "" if record.significant_variable else " hidden"
        title = escape(f"Variable star: {record.variability_type}", quote=True)
        parts.append(f'<span class="variable-star-marker" data-variable-star="true" data-significant="{str(record.significant_variable).lower()}" title="{title}"{hidden}>V</span>')
    if record.magnitude_display == "whole" and record.magnitude:
        parts.append(f'<span class="magnitude-normal">{whole_magnitude(record.magnitude)}</span>')
    elif record.magnitude_display == "literal" and record.magnitude:
        parts.append(f'<span class="magnitude-normal">{escape(record.magnitude)}</span>')
    if record.variability_type and record.variability_span is not None:
        bright, faint = one_decimal(record.variability_max_v), one_decimal(record.variability_min_v)
        parts.append(f'<span class="magnitude-variable-range" hidden>{escape(bright)}–{escape(faint)}</span>')
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
