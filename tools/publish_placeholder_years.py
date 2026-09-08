#!/usr/bin/env python3
"""Generate Star Almanack placeholder years with generic year navigation.

This is the production front end for the legacy placeholder renderer in
Star-Almanack-Repo/publish_placeholder_years.py.  The legacy module continues to
own the proven HTML/calendar rendering, while this wrapper supplies generic
navigation and an arbitrary list of ISO years.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "Star-Almanack-Repo" / "publish_placeholder_years.py"

spec = importlib.util.spec_from_file_location("placeholder_renderer", LEGACY)
renderer = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(renderer)


def parse_years() -> tuple[int, ...]:
    parser = argparse.ArgumentParser(description="Build placeholder Star Almanack ISO years")
    parser.add_argument("years", nargs="*", type=int, default=[2025, 2027])
    args = parser.parse_args()
    years = tuple(dict.fromkeys(args.years))
    if not years:
        parser.error("at least one year is required")
    for year in years:
        if year < 1583 or year > 9998:
            parser.error(f"unsupported Gregorian year: {year}")
    return years


def available_years(requested: tuple[int, ...]) -> tuple[int, ...]:
    """Return known Almanack years plus requested years, sorted."""
    known = {int(p.name) for p in renderer.OUT_ROOT.iterdir() if p.is_dir() and p.name.isdigit()}
    known.update(requested)
    return tuple(sorted(known))


def neighbors(year: int) -> tuple[int | None, int | None]:
    years = ACTIVE_YEARS
    idx = years.index(year)
    prev_year = years[idx - 1] if idx else None
    next_year = years[idx + 1] if idx + 1 < len(years) else None
    return prev_year, next_year


def shell(title: str, body: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · Star Almanack</title><style>{renderer.CSS}</style></head><body><header><div class="wrap"><div class="brand"><a href="/star-almanack/">Star Almanack</a></div><div class="subtitle">Alexander Ferrari Miller</div></div></header><main class="wrap"><nav class="weeknav sitenav"><a href="/star-almanack/">Almanack Home</a><a href="/projects.html">All Projects</a><a href="/index.html">Main Site</a></nav>{body}</main><footer><div class="wrap">© 2026 Alexander Ferrari Miller. All rights reserved.</div></footer>{renderer.SCRIPT}</body></html>'''


def year_nav(year: int) -> str:
    prev_year, next_year = neighbors(year)
    left = f'<a href="../{prev_year}/">← {prev_year}</a>' if prev_year is not None else '<span></span>'
    right = f'<a href="../{next_year}/">{next_year} →</a>' if next_year is not None else '<span></span>'
    return f'<nav class="yearnav">{left}<span>ISO {year}</span>{right}</nav>'


def week_nav(year: int, week: int) -> str:
    count = renderer.week_count(year)
    prev_year, next_year = neighbors(year)

    if week > 1:
        prev = f'<a href="../W{week-1:02d}/">← W{week-1:02d}</a>'
    elif prev_year is not None:
        prev_count = renderer.week_count(prev_year)
        prev = f'<a href="../../{prev_year}/W{prev_count:02d}/">← {prev_year}-W{prev_count:02d}</a>'
    else:
        prev = '<span class="disabled">← Previous</span>'

    if week < count:
        nxt = f'<a href="../W{week+1:02d}/">W{week+1:02d} →</a>'
    elif next_year is not None:
        nxt = f'<a href="../../{next_year}/W01/">{next_year}-W01 →</a>'
    else:
        nxt = '<span class="disabled">Next →</span>'

    return f'<nav class="weeknav">{prev}<a href="../">All {year} weeks</a>{nxt}</nav>'


def main() -> None:
    global ACTIVE_YEARS
    requested = parse_years()
    ACTIVE_YEARS = available_years(requested)

    renderer.shell = shell
    renderer.year_nav = year_nav
    renderer.week_nav = week_nav

    for year in requested:
        renderer.build_year(year)
    print("Published placeholder ISO-week calendars for " + ", ".join(map(str, requested)))


ACTIVE_YEARS: tuple[int, ...] = ()

if __name__ == "__main__":
    main()
