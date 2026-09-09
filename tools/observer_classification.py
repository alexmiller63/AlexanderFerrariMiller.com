#!/usr/bin/env python3
"""Shared observer-classification rules for Star Almanack stellar patterns.

Constellations and asterisms are classified from the median visual magnitude
of the stars that define the visible pattern. This module deliberately does
not classify extended deep-sky objects, whose integrated magnitude is not a
reliable proxy for practical observing equipment.
"""
from __future__ import annotations

from statistics import median
from typing import Iterable

NAKED_EYE_MAX_MEDIAN_V = 3.0
BINOCULAR_MAX_MEDIAN_V = 6.0

GLYPHS = {
    "naked_eye": '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/eye.svg" alt="Naked eye" aria-label="Naked eye" style="height:1.15em;width:auto;vertical-align:-.18em">',
    "binoculars": '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/binoculars.svg" alt="Binoculars" aria-label="Binoculars" style="height:1.15em;width:auto;vertical-align:-.18em">',
    "telescope": '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/telescope.svg" alt="Telescope" aria-label="Telescope" style="height:1.15em;width:auto;vertical-align:-.18em">',
}


def median_v(magnitudes: Iterable[float]) -> float:
    values = [float(value) for value in magnitudes]
    if not values:
        raise ValueError("observer classification requires at least one member-star magnitude")
    return float(median(values))


def observer_class_from_median_v(value: float) -> str:
    value = float(value)
    if value <= NAKED_EYE_MAX_MEDIAN_V:
        return "naked_eye"
    if value <= BINOCULAR_MAX_MEDIAN_V:
        return "binoculars"
    return "telescope"


def observer_class_for_members(magnitudes: Iterable[float]) -> tuple[float, str]:
    value = median_v(magnitudes)
    return value, observer_class_from_median_v(value)


def glyph_html(observer_class: str) -> str:
    try:
        return GLYPHS[observer_class]
    except KeyError as exc:
        raise ValueError(f"unknown observer class: {observer_class}") from exc
