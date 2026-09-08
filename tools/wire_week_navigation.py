#!/usr/bin/env python3
"""Keep Almanack year/week navigation clickable and visibly current."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASES = (ROOT / "almanack", ROOT / "Star-Almanack-Repo" / "site")
YEARS = (2025, 2026, 2027)

STYLE = """<style id="week-position-nav-css">
.yearnav .current-year,
.yearnav .current-year:visited {
  font-weight:700 !important;
  background:var(--soft-blue) !important;
  color:var(--navy) !important;
  border-color:#c8d3dc !important;
  text-decoration:none;
}
.weeknav.week-position .current-week {
  font-weight:700 !important;
  background:var(--navy) !important;
  color:#fff !important;
  border-color:var(--navy) !important;
}
.weekgrid a.current-week,
.weekgrid a.current-week:visited {
  font-weight:700 !important;
  background:var(--navy) !important;
  color:#fff !important;
  border-color:var(--navy) !important;
}
@media (prefers-color-scheme:dark) {
  .yearnav .current-year,
  .yearnav .current-year:visited {
    background:#1c2a36 !important;
    color:#eef7ff !important;
    border-color:#405567 !important;
  }
  .weeknav.week-position .current-week,
  .weekgrid a.current-week,
  .weekgrid a.current-week:visited {
    background:#eef7ff !important;
    color:#102a43 !important;
    border-color:#eef7ff !important;
  }
}
</style>"""

WEEK_NAV_RE = re.compile(r'<nav class="weeknav(?: week-position)?"(?: aria-label="Week navigation")?>(.*?)</nav>', re.S)
YEAR_NAV_RE = re.compile(r'<nav class="yearnav">(.*?)</nav>', re.S)
CHILD_RE = re.compile(r'(<a\b.*?</a>|<span\b.*?</span>)', re.S)
STYLE_RE = re.compile(r'<style id="week-position-nav-css">.*?</style>', re.S)


def set_text(tag: str, label: str) -> str:
    return re.sub(r'(?s)(>).*?(</(?:a|span)>)$', rf'\1{label}\2', tag, count=1)


def rewrite_year_nav(text: str, year: int, weekly_page: bool) -> str:
    match = YEAR_NAV_RE.search(text)
    if not match:
        raise RuntimeError("year navigation not found")
    children = CHILD_RE.findall(match.group(1))
    if len(children) < 3:
        raise RuntimeError("year navigation has fewer than 3 controls")
    left, right = children[0], children[-1]
    href = "../" if weekly_page else f"../{year}/"
    center = f'<a class="current-year" aria-current="page" href="{href}">{year}</a>'
    nav = f'<nav class="yearnav">{left}{center}{right}</nav>'
    return text[:match.start()] + nav + text[match.end():]


def rewrite_week_nav(text: str, year: int, week: int) -> str:
    match = WEEK_NAV_RE.search(text)
    if not match:
        raise RuntimeError("weekly navigation not found")
    children = CHILD_RE.findall(match.group(1))
    if len(children) < 2:
        raise RuntimeError("weekly navigation has fewer than 2 controls")

    ordinary = [c for c in children if 'current-week' not in c and 'all-weeks' not in c]
    if len(ordinary) >= 2:
        prev, nxt = ordinary[0], ordinary[-1]
    else:
        prev, nxt = children[0], children[-1]

    current = f'<span class="current-week" aria-current="page">ISO {year}-W{week:02d}</span>'
    nav = (
        '<nav class="weeknav week-position" aria-label="Week navigation">'
        f'{prev}{current}{nxt}'
        '</nav>'
    )
    return text[:match.start()] + nav + text[match.end():]


def ensure_style(text: str) -> str:
    if STYLE_RE.search(text):
        return STYLE_RE.sub(STYLE, text, count=1)
    if '</head>' not in text:
        raise RuntimeError("closing head tag not found")
    return text.replace('</head>', STYLE + '</head>', 1)


def highlight_current_week_on_index(text: str, year: int, week: int) -> str:
    text = re.sub(r' class="current-week"(?= aria-current="date" href="W\d{2}/")', '', text)
    target = f'href="W{week:02d}/"'
    if target not in text:
        raise RuntimeError(f"current week W{week:02d} not found on {year} index")
    text = text.replace(target, f'class="current-week" aria-current="date" {target}', 1)
    return ensure_style(text)


def main() -> None:
    changed = 0
    for base in BASES:
        for year in YEARS:
            for path in sorted((base / str(year)).glob('W??/index.html')):
                week = int(path.parent.name[1:])
                original = path.read_text(encoding='utf-8')
                updated = rewrite_year_nav(original, year, weekly_page=True)
                updated = rewrite_week_nav(updated, year, week)
                updated = ensure_style(updated)
                if updated != original:
                    path.write_text(updated, encoding='utf-8')
                    changed += 1

            index_path = base / str(year) / 'index.html'
            if index_path.exists():
                original = index_path.read_text(encoding='utf-8')
                updated = ensure_style(rewrite_year_nav(original, year, weekly_page=False))
                if updated != original:
                    index_path.write_text(updated, encoding='utf-8')
                    changed += 1

    today = datetime.now(timezone.utc).date().isocalendar()
    current_year, current_week = today.year, today.week
    if current_year in YEARS:
        for base in BASES:
            index_path = base / str(current_year) / 'index.html'
            if index_path.exists():
                original = index_path.read_text(encoding='utf-8')
                updated = highlight_current_week_on_index(original, current_year, current_week)
                if updated != original:
                    index_path.write_text(updated, encoding='utf-8')
                    changed += 1

    print(f"Updated year/week navigation on {changed} Almanack page copies")


if __name__ == '__main__':
    main()
