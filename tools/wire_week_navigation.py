#!/usr/bin/env python3
"""Add a highlighted ISO current-week position to generated Almanack week navigation."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path("almanack")
YEARS = (2025, 2026, 2027)

STYLE = """<style id="week-position-nav-css">
.weeknav.week-position .current-week {
  font-weight:700;
  background:var(--navy);
  color:#fff;
  border-color:var(--navy);
}
.weeknav.week-position .all-weeks {
  grid-column:1 / -1;
  justify-self:center;
}
@media (prefers-color-scheme:dark) {
  .weeknav.week-position .current-week {
    background:#eef7ff;
    color:#102a43;
    border-color:#eef7ff;
  }
}
</style>"""

NAV_RE = re.compile(r'<nav class="weeknav(?: week-position)?"(?: aria-label="Week navigation")?>(.*?)</nav>', re.S)
CHILD_RE = re.compile(r'(<a\b.*?</a>|<span\b.*?</span>)', re.S)
STYLE_RE = re.compile(r'<style id="week-position-nav-css">.*?</style>', re.S)


def add_class(tag: str, class_name: str) -> str:
    if re.search(r'\bclass="[^"]*"', tag):
        return re.sub(
            r'class="([^"]*)"',
            lambda m: f'class="{m.group(1)} {class_name}"' if class_name not in m.group(1).split() else m.group(0),
            tag,
            count=1,
        )
    return tag.replace('<a ', f'<a class="{class_name}" ', 1)


def set_text(tag: str, label: str) -> str:
    return re.sub(r'(?s)(>).*?(</(?:a|span)>)$', rf'\1{label}\2', tag, count=1)


def rewrite_nav(text: str, year: int, week: int) -> str:
    match = NAV_RE.search(text)
    if not match:
        raise RuntimeError("weekly navigation not found")

    children = CHILD_RE.findall(match.group(1))
    if len(children) < 3:
        raise RuntimeError("weekly navigation has fewer than 3 controls")

    ordinary = [c for c in children if 'current-week' not in c and 'all-weeks' not in c]
    if len(ordinary) >= 2:
        prev, nxt = ordinary[0], ordinary[-1]
    else:
        prev, nxt = children[0], children[-1]

    all_weeks = next((c for c in children if 'all-weeks' in c), None)
    if all_weeks is None:
        all_weeks = children[1]
    all_weeks = set_text(add_class(all_weeks, "all-weeks"), f"All {year} Weeks")

    current = f'<span class="current-week" aria-current="page">ISO {year}-W{week:02d}</span>'
    nav = (
        '<nav class="weeknav week-position" aria-label="Week navigation">'
        f'{prev}{current}{nxt}{all_weeks}'
        '</nav>'
    )
    return text[:match.start()] + nav + text[match.end():]


def ensure_style(text: str) -> str:
    if STYLE_RE.search(text):
        return STYLE_RE.sub(STYLE, text, count=1)
    if '</head>' not in text:
        raise RuntimeError("closing head tag not found")
    return text.replace('</head>', STYLE + '</head>', 1)


def main() -> None:
    changed = 0
    for year in YEARS:
        for path in sorted((ROOT / str(year)).glob('W??/index.html')):
            week = int(path.parent.name[1:])
            original = path.read_text(encoding='utf-8')
            updated = ensure_style(rewrite_nav(original, year, week))
            if updated != original:
                path.write_text(updated, encoding='utf-8')
                changed += 1
    print(f"Updated ISO week-position navigation on {changed} pages")


if __name__ == '__main__':
    main()
