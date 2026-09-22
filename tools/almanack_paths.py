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



def year_dir(year: int) -> Path:
    return ALMANACK_ROOT / str(year)


def week_dir(year: int, week: int) -> Path:
    return year_dir(year) / f"W{week:02d}"


def week_index(year: int, week: int) -> Path:
    return week_dir(year, week) / "index.html"



def weekly_pages(year: int | None = None) -> list[Path]:
    root = year_dir(year) if year is not None else ALMANACK_ROOT
    pattern = "W??/index.html" if year is not None else "20??/W??/index.html"
    return sorted(root.glob(pattern))
