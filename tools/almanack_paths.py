#!/usr/bin/env python3
"""Canonical filesystem paths for Star Almanack generators and audits.

All active Python tooling should use these helpers instead of reconstructing
YEAR/Www/type/index.html paths independently.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ALMANACK_ROOT = REPO_ROOT / "almanack"
GENERATED_ROOT = REPO_ROOT / "generated"
VISIBILITY_GLYPH_ROOT = "../../../../assets/almanack/visibility-glyphs/masters"

PAGE_TYPES = ("calendar", "ephemeris", "planet-finder", "sky-notes", "artwork")


def year_dir(year: int) -> Path:
    return ALMANACK_ROOT / str(year)


def week_dir(year: int, week: int) -> Path:
    return year_dir(year) / f"W{week:02d}"


def week_index(year: int, week: int) -> Path:
    return week_dir(year, week) / "index.html"


def typed_dir(year: int, week: int, page_type: str) -> Path:
    if page_type not in PAGE_TYPES:
        raise ValueError(f"Unknown Almanack page type: {page_type}")
    return week_dir(year, week) / page_type


def typed_page(year: int, week: int, page_type: str) -> Path:
    return typed_dir(year, week, page_type) / "index.html"


def calendar_page(year: int, week: int) -> Path:
    return typed_page(year, week, "calendar")


def ephemeris_page(year: int, week: int) -> Path:
    return typed_page(year, week, "ephemeris")


def planet_finder_page(year: int, week: int) -> Path:
    return typed_page(year, week, "planet-finder")


def sky_notes_page(year: int, week: int) -> Path:
    return typed_page(year, week, "sky-notes")


def artwork_page(year: int, week: int) -> Path:
    return typed_page(year, week, "artwork")


def calendar_pages(year: int | None = None) -> list[Path]:
    root = year_dir(year) if year is not None else ALMANACK_ROOT
    pattern = "W??/calendar/index.html" if year is not None else "20??/W??/calendar/index.html"
    return sorted(root.glob(pattern))
