#!/usr/bin/env python3
"""Keep Almanack year/week navigation clickable and visibly current."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASES = (ROOT / "almanack", ROOT / "Star-Almanack-Repo" / "site")
YEARS = (2025, 2026, 2027)
BOTTOM_ID = "almanack-bottom-nav"

STYLE = """<style id="week-position-nav-css">
.yearnav .current-year,
.yearnav .current-year:visited,
.weeknav.week-position .current-week,
.weekgrid a.current-week,
.weekgrid a.current-week:visited {
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
  .yearnav .current-year,
  .yearnav .current-year:visited,
  .weeknav.week-position .current-week,
  .weekgrid a.current-week,
  .weekgrid a.current-week:visited {
    background:#eef7ff !important;
    color:#102a43 !important;
    border-color:#eef7ff !important;
  }
}
</style>"""

WEEK_NAV_RE = re.compile(r'<nav class="weeknav(?: week-position)?"(?: id="(?:week-bottom-nav|almanack-bottom-nav)")?(?: aria-label="Week navigation")?>(.*?)</nav>', re.S)
YEAR_NAV_RE = re.compile(r'<nav class="yearnav"(?: id="almanack-bottom-nav")?>(.*?)</nav>', re.S)
SITE_NAV_RE = re.compile(r'<nav class="weeknav sitenav">(.*?)</nav>', re.S)
BOTTOM_WRAP_RE = re.compile(r'<div class="almanack-bottom-nav-wrap" id="almanack-bottom-nav">.*?</div>', re.S)
EMPTY_BOTTOM_RE = re.compile(r'<div id="almanack-bottom-nav"></div>')
CHILD_RE = re.compile(r'(<a\b.*?</a>|<span\b.*?</span>)', re.S)
STYLE_RE = re.compile(r'<style id="week-position-nav-css">.*?</style>', re.S)
HREF_RE = re.compile(r'href="([^"]+)"')


def href_of(tag: str) -> str:
    m = HREF_RE.search(tag)
    return m.group(1) if m else ""


def add_bottom_fragment_to_tag(tag: str) -> str:
    def repl(match: re.Match[str]) -> str:
        href = match.group(1).split('#', 1)[0]
        return f'href="{href}#{BOTTOM_ID}"'
    return HREF_RE.sub(repl, tag)


def rewrite_year_nav(text: str, year: int, weekly_page: bool) -> str:
    match = YEAR_NAV_RE.search(text)
    if not match:
        raise RuntimeError("year navigation not found")
    children = CHILD_RE.findall(match.group(1))

    previous = None
    following = None
    for child in children:
        if not child.startswith("<a"):
            continue
        href = href_of(child)
        if str(year - 1) in href or re.search(rf'\b{year - 1}\b', child):
            previous = child
        elif str(year + 1) in href or re.search(rf'\b{year + 1}\b', child):
            following = child

    left = previous or '<span class="nav-spacer" aria-hidden="true">—</span>'
    right = following or '<span class="nav-spacer" aria-hidden="true">—</span>'
    href = "../" if weekly_page else "./"
    if weekly_page:
        center = f'<a href="{href}">{year}</a>'
    else:
        center = f'<a class="current-year" aria-current="page" href="{href}">{year}</a>'
    nav = f'<nav class="yearnav">{left}{center}{right}</nav>'
    return text[:match.start()] + nav + text[match.end():]


def week_target(tag: str) -> int | None:
    href = href_of(tag)
    m = re.search(r'W(\d{2})', href)
    return int(m.group(1)) if m else None


def build_week_nav_from_match(match: re.Match[str], year: int, week: int) -> str:
    children = CHILD_RE.findall(match.group(1))

    previous = None
    following = None
    for child in children:
        if not child.startswith("<a"):
            continue
        target = week_target(child)
        if target == week - 1:
            previous = child
        elif target == week + 1:
            following = child

    left = previous or '<span class="nav-spacer" aria-hidden="true">—</span>'
    right = following or '<span class="nav-spacer" aria-hidden="true">—</span>'
    current = f'<span class="current-week" aria-current="page">ISO {year}-W{week:02d}</span>'
    return (
        '<nav class="weeknav week-position" aria-label="Week navigation">'
        f'{left}{current}{right}'
        '</nav>'
    )


def rewrite_week_nav(text: str, year: int, week: int) -> str:
    matches = list(WEEK_NAV_RE.finditer(text))
    if not matches:
        raise RuntimeError("weekly navigation not found")

    top = build_week_nav_from_match(matches[0], year, week)
    index = 0

    def replacement(_: re.Match[str]) -> str:
        nonlocal index
        index += 1
        return top if index == 1 else ""

    return WEEK_NAV_RE.sub(replacement, text)


def bottom_site_nav(text: str) -> str:
    match = SITE_NAV_RE.search(text)
    if not match:
        raise RuntimeError("site navigation not found")
    nav = match.group(0)

    def rewrite_link(link_match: re.Match[str]) -> str:
        tag = link_match.group(0)
        if "Almanack Home" in tag:
            return add_bottom_fragment_to_tag(tag)
        return tag

    return re.sub(r'<a\b.*?</a>', rewrite_link, nav, flags=re.S)


def bottom_year_nav(text: str, year: int) -> str:
    match = YEAR_NAV_RE.search(text)
    if not match:
        raise RuntimeError("year navigation not found")
    nav = match.group(0)
    nav = re.sub(
        rf'<a href="([^"]+)">{year}</a>',
        rf'<a class="current-year" aria-current="page" href="\1">{year}</a>',
        nav,
        count=1,
    )
    return HREF_RE.sub(
        lambda m: f'href="{m.group(1).split("#", 1)[0]}#{BOTTOM_ID}"',
        nav,
    )


def bottom_week_nav(text: str) -> str:
    match = re.search(r'<nav class="weeknav week-position" aria-label="Week navigation">.*?</nav>', text, re.S)
    if not match:
        raise RuntimeError("week position navigation not found")
    return HREF_RE.sub(
        lambda m: f'href="{m.group(1).split("#", 1)[0]}#{BOTTOM_ID}"',
        match.group(0),
    )


def place_bottom_navigation(text: str, year: int) -> str:
    text = BOTTOM_WRAP_RE.sub("", text)
    block = (
        f'<div class="almanack-bottom-nav-wrap" id="{BOTTOM_ID}">'
        f'{bottom_site_nav(text)}'
        f'{bottom_year_nav(text, year)}'
        f'{bottom_week_nav(text)}'
        '</div>'
    )
    if '</aside>' not in text:
        raise RuntimeError("notation legend not found")
    return text.replace('</aside>', '</aside>' + block, 1)


def ensure_year_bottom_target(text: str, year: int) -> str:
    """Give year indexes the same first two bottom-nav rows as week pages."""
    text = BOTTOM_WRAP_RE.sub("", text)
    text = EMPTY_BOTTOM_RE.sub("", text)
    matches = list(YEAR_NAV_RE.finditer(text))
    if not matches:
        raise RuntimeError("year navigation not found")

    match = matches[-1]
    nav = match.group(0)
    # The generated year-index bottom center has historically been a span
    # (for example, "ISO 2026"). Replace it with the active-year link so the
    # same current-year styling used by the top row is applied at the bottom.
    children = CHILD_RE.findall(match.group(1))
    left = children[0] if children else '<span class="nav-spacer" aria-hidden="true">—</span>'
    right = children[-1] if len(children) > 1 else '<span class="nav-spacer" aria-hidden="true">—</span>'
    center = f'<a class="current-year" aria-current="page" href="./#{BOTTOM_ID}">ISO {year}</a>'
    nav = f'<nav class="yearnav">{left}{center}{right}</nav>'
    nav = HREF_RE.sub(
        lambda m: f'href="{m.group(1).split("#", 1)[0]}#{BOTTOM_ID}"',
        nav,
    )
    block = (
        f'<div class="almanack-bottom-nav-wrap" id="{BOTTOM_ID}">'
        f'{bottom_site_nav(text)}'
        f'{nav}'
        '</div>'
    )
    return text[:match.start()] + block + text[match.end():]


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
    for base in BASES:
        for year in YEARS:
            for path in sorted((base / str(year)).glob('W??/index.html')):
                week = int(path.parent.name[1:])
                original = path.read_text(encoding='utf-8')
                updated = rewrite_year_nav(original, year, weekly_page=True)
                updated = rewrite_week_nav(updated, year, week)
                updated = place_bottom_navigation(updated, year)
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

    print(f"Updated {changed} Almanack navigation page(s).")


if __name__ == '__main__':
    main()
