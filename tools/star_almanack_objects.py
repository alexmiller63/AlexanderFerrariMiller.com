#!/usr/bin/env python3
"""Shared semantic object model and reader-facing rendering for the Star Almanack.

Astronomical/source data owns identity, type, magnitude data, provenance, and the
semantic observing aid. Derived astronomy and reader-facing presentation are
centralized here. Detail: Standard uses whole magnitudes and marks only variables
spanning at least 1.0 V magnitude. Detail: All exposes one-decimal magnitudes for
all objects and reveals every catalogued variable with its one-decimal range.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from html import escape
from pathlib import Path

from almanack_paths import VISIBILITY_GLYPH_ROOT
from star_almanack_astronomy import declination_band, season_for


class ObservingAid(str, Enum):
    NAKED_EYE = "naked_eye"
    BINOCULARS = "binoculars"
    TELESCOPE = "telescope"


TEXT_AID = {ObservingAid.NAKED_EYE: "👁", ObservingAid.BINOCULARS: "B", ObservingAid.TELESCOPE: "🔭"}
HTML_AID = {
    ObservingAid.NAKED_EYE: f'<img class="visibility-glyph" src="{VISIBILITY_GLYPH_ROOT}/eye.svg" alt="Naked eye" aria-label="Naked eye">',
    ObservingAid.BINOCULARS: f'<img class="visibility-glyph" src="{VISIBILITY_GLYPH_ROOT}/binoculars.svg" alt="Binoculars" aria-label="Binoculars">',
    ObservingAid.TELESCOPE: f'<img class="visibility-glyph" src="{VISIBILITY_GLYPH_ROOT}/telescope.svg" alt="Telescope" aria-label="Telescope">',
}
GCVS_GREEK = {'α':'alf','β':'bet','γ':'gam','δ':'del','ε':'eps','ζ':'zet','η':'eta','θ':'the','ι':'iot','κ':'kap','λ':'lam','μ':'mu','ν':'nu','ξ':'xi','ο':'omi','π':'pi','ρ':'rho','σ':'sig','τ':'tau','υ':'ups','φ':'phi','χ':'chi','ψ':'psi','ω':'ome'}


def _load_variable_catalog():
    path = Path(__file__).resolve().parents[1] / "bright-variable-reconciliation.csv"
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {row["name"].strip().lower(): row for row in csv.DictReader(f) if row.get("name")}


VARIABLE_CATALOG = _load_variable_catalog()


def observing_aid_for_magnitude(value: str) -> ObservingAid | None:
    try: mag = float((value or "").strip())
    except ValueError: return None
    if mag <= 3.5: return ObservingAid.NAKED_EYE
    if mag <= 7.5: return ObservingAid.BINOCULARS
    return ObservingAid.TELESCOPE


def whole_magnitude(value: str) -> str:
    value = (value or "").strip()
    if not value: return ""
    try: rounded = Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except InvalidOperation: return value
    return str(int(rounded))


def one_decimal(value: str) -> str:
    try: return str(Decimal((value or "").strip()).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    except InvalidOperation: return (value or "").strip()


def adaptive_variable_range(bright: str, faint: str) -> tuple[str, str]:
    """Format a variable-star range compactly without rounding away variability."""
    try:
        a = Decimal((bright or "").strip())
        b = Decimal((faint or "").strip())
    except InvalidOperation:
        return (bright or "").strip(), (faint or "").strip()
    for places in (1, 2, 3):
        quantum = Decimal(1).scaleb(-places)
        qa = a.quantize(quantum, rounding=ROUND_HALF_UP)
        qb = b.quantize(quantum, rounding=ROUND_HALF_UP)
        if qa != qb or a == b or places == 3:
            return f"{qa:.{places}f}", f"{qb:.{places}f}"
    return str(a), str(b)


def _variable_row_for_label(label: str):
    match = re.search(r"([αβγδεζηθικλμνξοπρστυφχψω])(\d*)\s+([A-Z][A-Za-z]{2})", label or "")
    if not match: return None
    stem = GCVS_GREEK.get(match.group(1))
    if not stem: return None
    key = f"{stem}{(' ' + match.group(2)) if match.group(2) else ''} {match.group(3)}".lower()
    return VARIABLE_CATALOG.get(key)


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
    def band(self) -> str: return declination_band(self.dec_deg)

    @property
    def season(self) -> str: return season_for(self.best_date)

    @property
    def variability_values(self) -> tuple[str, str]:
        if self.variability_max_v and self.variability_min_v:
            return self.variability_max_v, self.variability_min_v
        row = _variable_row_for_label(self.label) if self.variability_type else None
        return ((row.get("gcvs_max_v") or "").strip(), (row.get("gcvs_min_v") or "").strip()) if row else ("", "")

    @property
    def variability_span(self) -> float | None:
        bright, faint = self.variability_values
        try: return abs(float(faint) - float(bright))
        except (TypeError, ValueError): return None

    @property
    def significant_variable(self) -> bool:
        span = self.variability_span
        return bool(self.variability_type and span is not None and span >= 1.0)


def visibility_text(record: AlmanackObject) -> str:
    if record.observing_aid is None: return ""
    parts = [TEXT_AID[record.observing_aid]]
    if record.significant_variable: parts.append("V")
    if record.magnitude_display == "whole" and record.magnitude: parts.append(whole_magnitude(record.magnitude))
    elif record.magnitude_display == "literal" and record.magnitude: parts.append(record.magnitude)
    return " ".join(parts)


def visibility_html(record: AlmanackObject) -> str:
    if record.observing_aid is None: return ""
    parts = [HTML_AID[record.observing_aid]]
    bright, faint = record.variability_values
    if record.variability_type and record.variability_span is not None:
        hidden = "" if record.significant_variable else " hidden"
        title = escape(f"Variable star: {record.variability_type}", quote=True)
        parts.append(f'<span class="variable-star-marker" data-variable-star="true" data-significant="{str(record.significant_variable).lower()}" title="{title}"{hidden}>V</span>')
    if record.magnitude_display == "whole" and record.magnitude:
        parts.append(f'<span class="magnitude-normal">{whole_magnitude(record.magnitude)}</span>')
        parts.append(f'<span class="magnitude-detail" hidden>{escape(one_decimal(record.magnitude))}</span>')
    elif record.magnitude_display == "literal" and record.magnitude:
        parts.append(f'<span class="magnitude-normal">{escape(record.magnitude)}</span>')
        parts.append(f'<span class="magnitude-detail" hidden>{escape(one_decimal(record.magnitude))}</span>')
    if record.variability_type and record.variability_span is not None:
        range_bright, range_faint = adaptive_variable_range(bright, faint)
        parts.append(f'<span class="magnitude-variable-range" hidden>{escape(range_bright)}–{escape(range_faint)}</span>')
    return " ".join(parts)


def classification_text(record: AlmanackObject) -> str: return f"{record.band} {record.season}"


def render_text(record: AlmanackObject) -> str:
    parts = [record.label]; visibility = visibility_text(record)
    if visibility: parts.append(visibility)
    parts.append(classification_text(record)); return " — ".join(parts)


def render_html(record: AlmanackObject) -> str:
    parts = [record.label]; visibility = visibility_html(record)
    if visibility: parts.append(f'<span class="visibility-magnitude">{visibility}</span>')
    parts.append(classification_text(record)); return " — ".join(parts)
