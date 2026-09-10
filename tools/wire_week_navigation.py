#!/usr/bin/env python3
"""Keep Almanack year/week navigation clickable and positionally correct."""

from __future__ import annotations

import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BASES = (ROOT / "almanack", ROOT / "Star-Almanack-Repo" / "site")
BOTTOM_ID = "almanack-bottom-nav"
LOCAL_ZONE = ZoneInfo("America/Los_Angeles")

STYLE = """<style id="week-position-nav-css">
.weekgrid a.current-week,
.weekgrid a.current-week:visited,
.weeknav span[aria-current="page"] {
  font-weight:700 !important;
  background:var(--navy) !important;
  color:#fff !important;
  border-color:var(--navy) !important;
  text-decoration:none;
}
.yearnav .nav-spacer,
.weeknav .nav-spacer {
  visibility:hidden;
}
.almanack-bottom-nav-wrap {
  max-width:1080px;
  margin:0 auto;
  padding:1rem 1.5rem 1.5rem;
}
.almanack-bottom-nav-wrap nav:last-child {
  margin-bottom:0;
}
@media (orientation:landscape) and (max-height:500px) {
  .almanack-bottom-nav-wrap {
    padding:.55rem 1rem .75rem;
  }
  .almanack-bottom-nav-wrap .weeknav,
  .almanack-bottom-nav-wrap .yearnav {
    gap:.45rem;
    margin:.2rem 0 .55rem;
    font-size:.82rem;
  }
  .almanack-bottom-nav-wrap .weeknav a,
  .almanack-bottom-nav-wrap .weeknav span,
  .almanack-bottom-nav-wrap .yearnav a,
  .almanack-bottom-nav-wrap .yearnav span {
    min-width:0;
    padding:.4rem .55rem;
  }
}
@media (prefers-color-scheme:dark) {
  .weekgrid a.current-week,
  .weekgrid a.current-week:visited,
  .weeknav span[aria-current="page"] {
    background:#eef7ff !important;
    color:#102a43 !important;
    border-color:#eef7ff !important;
  }
}
</style>"""

WEEK_NAV_RE = re.compile(r'<nav class="weeknav(?: week-position)?"(?: id="(?:week-bottom-nav|almanack-bottom-nav)")?(?: aria-label="Week navigation")?>(.*?)</nav>', re.S)
YEAR_NAV_RE = re.compile(r'<nav class="yearnav"(?: id="almanack-bottom-nav")?>(.*?)</nav>', re.S)
BOTTOM_WRAP_RE = re.compile(r'<div class="almanack-bottom-nav-wrap" id="almanack-bottom-nav">.*?</div>', re.S)
EMPTY_BOTTOM_RE = re.compile(r'<div id="almanack-bottom-nav"></div>')
STYLE_RE = re.compile(r'<style id="week-position-nav-css">.*?</style>', re.S)


def published_years() -> tuple[int, ...]:
    discovered: set[int] = set()
    for base in BASES:
        if not base.exists():
            continue
        for path in base.iterdir():
            if path.is_dir() and re.fullmatch(r"\d{4}", path.name) and (path / "index.html").exists():
                discovered.add(int(path.name))
    return tuple(sorted(discovered))


def requested_years() -> tuple[int, ...]:
    if len(sys.argv) > 1:
        try:
            years = tuple(dict.fromkeys(int(arg) for arg in sys.argv[1:]))
        except ValueError as exc:
            raise SystemExit("Years must be integers, e.g. 2025 2027") from exc
        if any(year < 1 for year in years):
            raise SystemExit("Years must be positive integers")
        return years
    return published_years()


def adjacent_published_year(year: int, direction: int) -> int | None:
    years = published_years()
    if direction < 0:
        earlier = [candidate for candidate in years if candidate < year]
        return max(earlier) if earlier else None
    later = [candidate for candidate in years if candidate > year]
    return min(later) if later else None


def build_year_nav(year: int, weekly_page: bool, bottom: bool = False) -> str:
    previous = adjacent_published_year(year, -1)
    following = adjacent_published_year(year, 1)

    def href(target: int) -> str:
        base = f"../../{target}/" if weekly_page else f"../{target}/"
        return base + (f"#{BOTTOM_ID}" if bottom else "")

    left = (
        f'<a href="{href(previous)}">← {previous}</a>'
        if previous is not None else
        '<span class="nav-spacer" aria-hidden="true">—</span>'
    )
    right = (
        f'<a href="{href(following)}">{following} →</a>'
        if following is not None else
        '<span class="nav-spacer" aria-hidden="true">—</span>'
    )
    if weekly_page:
        center_href = "../" + (f"#{BOTTOM_ID}" if bottom else "")
        center = f'<a href="{center_href}">{year}</a>'
    else:
        center = f'<span aria-current="page">{year}</span>'
    return f'<nav class="yearnav">{left}{center}{right}</nav>'


def rewrite_year_nav(text: str, year: int, weekly_page: bool) -> str:
    match = YEAR_NAV_RE.search(text)
    if not match:
        raise RuntimeError("year navigation not found")
    nav = build_year_nav(year, weekly_page)
    return text[:match.start()] + nav + text[match.end():]


def adjacent_week(year: int, week: int, days: int) -> tuple[int, int]:
    monday = date.fromisocalendar(year, week, 1)
    target = (monday + timedelta(days=days)).isocalendar()
    return target.year, target.week


def adjacent_week_link(year: int, week: int, days: int, bottom: bool = False) -> str:
    target_year, target_week = adjacent_week(year, week, days)
    if target_year == year:
        href = f'../W{target_week:02d}/'
    else:
        href = f'../../{target_year}/W{target_week:02d}/'
    if bottom:
        href += f'#{BOTTOM_ID}'
    label = f'ISO {target_year}-W{target_week:02d}'
    if days < 0:
        return f'<a href="{href}">← {label}</a>'
    return f'<a href="{href}">{label} →</a>'


def build_week_nav(year: int, week: int, bottom: bool = False) -> str:
    left = adjacent_week_link(year, week, -7, bottom)
    right = adjacent_week_link(year, week, 7, bottom)
    current = f'<span aria-current="page">ISO {year}-W{week:02d}</span>'
    return (
        '<nav class="weeknav week-position" aria-label="Week navigation">'
        f'{left}{current}{right}'
        '</nav>'
    )


def rewrite_week_nav(text: str, year: int, week: int) -> str:
    matches = list(WEEK_NAV_RE.finditer(text))
    if not matches:
        raise RuntimeError("weekly navigation not found")
    top = build_week_nav(year, week)
    index = 0

    def replacement(_: re.Match[str]) -> str:
        nonlocal index
        index += 1
        return top if index == 1 else ""

    return WEEK_NAV_RE.sub(replacement, text)


def place_bottom_navigation(text: str, year: int, week: int) -> str:
    """Replace the bottom navigation with year/week controls only; site navigation stays top-only."""
    text = BOTTOM_WRAP_RE.sub("", text)
    block = (
        f'<div class="almanack-bottom-nav-wrap" id="{BOTTOM_ID}">'
        f'{build_year_nav(year, weekly_page=True, bottom=True)}'
        f'{build_week_nav(year, week, bottom=True)}'
        '</div>'
    )
    if '</aside>' not in text:
        raise RuntimeError("notation legend not found")
    return text.replace('</aside>', '</aside>' + block, 1)


def ensure_year_bottom_target(text: str, year: int) -> str:
    """Give year indexes canonical year navigation at the bottom without duplicating site navigation."""
    text = BOTTOM_WRAP_RE.sub("", text)
    text = EMPTY_BOTTOM_RE.sub("", text)
    block = (
        f'<div class="almanack-bottom-nav-wrap" id="{BOTTOM_ID}">'
        f'{build_year_nav(year, weekly_page=False, bottom=True)}'
        '</div>'
    )
    if '</aside>' in text:
        return text.replace('</aside>', '</aside>' + block, 1)
    if '</main>' in text:
        return text.replace('</main>', block + '</main>', 1)
    raise RuntimeError("year bottom navigation insertion point not found")


def ensure_style(text: str) -> str:
    if STYLE_RE.search(text):
        return STYLE_RE.sub(STYLE, text, count=1)
    if '</head>' not in text:
        raise RuntimeError("closing head tag not found")
    return text.replace('</head>', STYLE + '</head>', 1)


def highlight_current_week_on_index(text: str, year: int, week: int) -> str:
    text = re.sub(r'\sclass="current-week"', '', text)
    text = re.sub(r'\saria-current="date"', '', text)
    target = f'href="W{week:02d}/"'
    if target not in text:
        raise RuntimeError(f"current week W{week:02d} not found on {year} index")
    text = text.replace(target, f'class="current-week" aria-current="date" {target}', 1)
    return ensure_style(text)


def main() -> None:
    changed = 0
    years = requested_years()
    for base in BASES:
        for year in years:
            for path in sorted((base / str(year)).glob('W??/index.html')):
                week = int(path.parent.name[1:])
                original = path.read_text(encoding='utf-8')
                updated = rewrite_year_nav(original, year, weekly_page=True)
                updated = rewrite_week_nav(updated, year, week)
                updated = place_bottom_navigation(updated, year, week)
                updated = ensure_style(updated)
                if updated != original:
                    path.write_text(updated, encoding='utf-8')
                    changed += 1

            index_path = base / str(year) / 'index.html'
            if index_path.exists():
                original = index_path.read_text(encoding='utf-8')
                updated = ensure_style(rewrite_year_nav(original, year, weekly_page=False))
                updated = ensure_year_bottom_target(updated, year)
                if updated != original:
                    index_path.write_text(updated, encoding='utf-8')
                    changed += 1

    today = datetime.now(LOCAL_ZONE).date().isocalendar()
    current_year, current_week = today.year, today.week
    if current_year in years:
        for base in BASES:
            index_path = base / str(current_year) / 'index.html'
            if index_path.exists():
                original = index_path.read_text(encoding='utf-8')
                updated = highlight_current_week_on_index(original, current_year, current_week)
                if updated != original:
                    index_path.write_text(updated, encoding='utf-8')
                    changed += 1

    print(f"Updated {changed} Almanack navigation page(s) for: {' '.join(map(str, years))}.")


if __name__ == '__main__':
    main()
