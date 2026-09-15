#!/usr/bin/env python3
"""Create clean Star Almanack weekly page shells for an inclusive ISO-week range.

This is the canonical scaffold stage for the public Almanack. It deliberately
contains no astronomy: later generators own Calendar, Sky Notes, artwork,
Ephemeris, Planet Finder, notation, and legend content.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOT = ROOT / "almanack"
BOTTOM_ID = "almanack-bottom-nav"

CSS = r"""
:root{color-scheme:light dark;--ink:#202833;--muted:#66717d;--navy:#102a43;--link:#245c86;--paper:#fffdf8;--page:#eee9df;--rule:#d8d2c8}
*{box-sizing:border-box}html{font-size:17px}body{margin:0;font-family:Georgia,'Times New Roman',serif;line-height:1.65;background:var(--page);color:var(--ink)}a,a:visited{color:var(--link)}header,footer{background:var(--navy);color:#fff}header{border-bottom:4px solid #c5a45c}header a,header a:visited,footer a,footer a:visited{color:#eef7ff}.wrap{max-width:1080px;margin:0 auto;padding:1.15rem 1.5rem}main.wrap{background:var(--paper);min-height:76vh;padding:2rem 2.4rem 3.25rem}.brand{font-size:1.35rem;font-weight:700}.subtitle{opacity:.86;font-size:.94rem}.weeknav,.yearnav{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:.8rem;margin:.4rem 0 1rem;font-family:system-ui,sans-serif;font-size:.9rem}.weeknav>:last-child,.yearnav>:last-child{justify-self:end}.weeknav a,.weeknav span,.yearnav a,.yearnav span{display:inline-block;min-width:5.5rem;padding:.58rem .8rem;border:1px solid #c8d3dc;border-radius:.45rem;text-decoration:none;text-align:center;background:#fff;color:var(--link)}.weeknav span[aria-current="page"],.yearnav span[aria-current="page"]{font-weight:700;background:var(--navy);color:#fff;border-color:var(--navy)}.nav-spacer{visibility:hidden}.almanack-bottom-nav-wrap{margin-top:2rem}h1,h2,h3{line-height:1.2;color:#17344d}h1{font-size:clamp(2rem,5vw,2.75rem)}h3{margin-top:2rem}table{width:100%;border-collapse:separate;border-spacing:0;margin:1rem 0 2rem;font-family:system-ui,sans-serif;font-size:.93rem;border:1px solid #cbd3da;border-radius:.5rem;overflow:hidden}th,td{padding:.7rem .8rem;border-right:1px solid #d6dde3;border-bottom:1px solid #d6dde3;vertical-align:top}th:last-child,td:last-child{border-right:0}tbody tr:last-child td{border-bottom:0}th{background:#e8f0f5;text-align:left;color:#17344d}.calendar{table-layout:fixed}.calendar th:first-child,.calendar td:first-child{width:28%}.calendar th:nth-child(2),.calendar td:nth-child(2){width:20%;text-align:center}.calendar th:nth-child(3),.calendar td:nth-child(3){width:52%}.ephemeris{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}.ephemeris th,.ephemeris td{text-align:center;white-space:nowrap}.sky-note{border-left:3px solid #c8d3dc;padding-left:1rem}footer{font-family:system-ui,sans-serif;font-size:.88rem}@media(max-width:760px){html{font-size:16px}.wrap{padding-left:1rem;padding-right:1rem}main.wrap{padding:1.35rem 1rem 2.5rem}.weeknav,.yearnav{gap:.4rem}.weeknav a,.weeknav span,.yearnav a,.yearnav span{min-width:0;padding:.6rem .45rem}}@media(prefers-color-scheme:dark){:root{--ink:#dce6ef;--muted:#a7b4c0;--link:#9fd0ff;--paper:#17212b;--page:#10171f;--rule:#394957}h1,h2,h3{color:#f1f7fb}th{background:#223444;color:#eef7ff}th,td,table{border-color:#40505e}.weeknav a,.weeknav span,.yearnav a,.yearnav span{background:#1c2a36;border-color:#405567;color:#b6dcff}.weeknav span[aria-current="page"],.yearnav span[aria-current="page"]{background:#eef7ff;color:#102a43;border-color:#eef7ff}}
""".strip()


def week_count(year: int) -> int:
    return dt.date(year, 12, 28).isocalendar().week


def validate(year: int, week: int) -> None:
    if year < 1583 or year > 9998:
        raise ValueError(f"unsupported Gregorian year: {year}")
    if week < 1 or week > week_count(year):
        raise ValueError(f"ISO {year} has no week {week}")


def selected_weeks(sy: int, sw: int, ey: int, ew: int):
    validate(sy, sw); validate(ey, ew)
    start = dt.date.fromisocalendar(sy, sw, 1)
    end = dt.date.fromisocalendar(ey, ew, 1)
    if end < start:
        raise ValueError("end week precedes start week")
    d = start
    while d <= end:
        y, w, _ = d.isocalendar()
        yield y, w, d
        d += dt.timedelta(days=7)


def published_years() -> tuple[int, ...]:
    if not PUBLIC_ROOT.exists():
        return ()
    return tuple(sorted(int(p.name) for p in PUBLIC_ROOT.iterdir()
                        if p.is_dir() and p.name.isdigit() and (p / "index.html").exists()))


def year_nav(year: int, bottom: bool = False) -> str:
    years = published_years()
    previous = max((y for y in years if y < year), default=None)
    following = min((y for y in years if y > year), default=None)
    suffix = f"#{BOTTOM_ID}" if bottom else ""
    left = f'<a href="../../{previous}/{suffix}">← {previous}</a>' if previous is not None else '<span class="nav-spacer" aria-hidden="true">—</span>'
    center = f'<a href="../{suffix}">{year}</a>'
    right = f'<a href="../../{following}/{suffix}">{following} →</a>' if following is not None else '<span class="nav-spacer" aria-hidden="true">—</span>'
    return f'<nav class="yearnav">{left}{center}{right}</nav>'


def adjacent_week(year: int, week: int, days: int) -> tuple[int, int]:
    target = (dt.date.fromisocalendar(year, week, 1) + dt.timedelta(days=days)).isocalendar()
    return target.year, target.week


def week_link(year: int, week: int, days: int, bottom: bool = False) -> str:
    ty, tw = adjacent_week(year, week, days)
    if ty == year:
        href = f'../W{tw:02d}/'
    else:
        href = f'../../{ty}/W{tw:02d}/'
    if bottom:
        href += f'#{BOTTOM_ID}'
    label = f'ISO {ty}-W{tw:02d}'
    return f'<a href="{href}">← {label}</a>' if days < 0 else f'<a href="{href}">{label} →</a>'


def week_nav(year: int, week: int, bottom: bool = False) -> str:
    return ('<nav class="weeknav week-position" aria-label="Week navigation">'
            + week_link(year, week, -7, bottom)
            + f'<span aria-current="page">ISO {year}-W{week:02d}</span>'
            + week_link(year, week, 7, bottom)
            + '</nav>')


def site_nav() -> str:
    return '<nav class="weeknav sitenav"><a href="/star-almanack/">Almanack Home</a><a href="/projects.html">All Projects</a><a href="/index.html">Main Site</a></nav>'


def nav_stack(year: int, week: int, bottom: bool = False) -> str:
    return site_nav() + year_nav(year, bottom) + week_nav(year, week, bottom)


def calendar_rows(monday: dt.date) -> str:
    rows = []
    for offset in range(7):
        d = monday + dt.timedelta(days=offset)
        label = f'{d.strftime("%a, %b")} {d.day}, {d.year}'
        rows.append(f'<tr data-date="{d.isoformat()}"><td>{label}</td><td data-zodiac-day="">—</td><td data-events>—</td></tr>')
    return ''.join(rows)


def page(year: int, week: int, monday: dt.date) -> str:
    title = f'ISO {year}-W{week:02d}'
    rows = calendar_rows(monday)
    top_nav = nav_stack(year, week)
    bottom_nav = f'<div class="almanack-bottom-nav-wrap" id="{BOTTOM_ID}">{nav_stack(year, week, True)}</div>'
    body = f'''{top_nav}<h1>{title}</h1><p><strong>Week begins:</strong> {monday.strftime("Monday, %B")} {monday.day}, {monday.year}</p>
<h3>Calendar</h3><table class="calendar"><thead><tr><th>Date</th><th>Zodiac day</th><th>Events</th></tr></thead><tbody>{rows}</tbody></table>
<h3>Weekly Solar-System Ephemeris</h3><p><strong>Snapshot:</strong> pending</p><table class="ephemeris"><thead><tr><th>Sun</th><th>Moon</th><th>Mercury</th><th>Venus</th><th>Mars</th><th>Jupiter</th><th>Saturn</th></tr></thead><tbody><tr><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td></tr></tbody></table>
<h3>Planet Finder</h3><div class="planet-finder-block"><p>Planet finder pending.</p></div>
<h3>Sky Notes</h3><div class="sky-note"><p>Sky notes pending.</p></div>{bottom_nav}'''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · Star Almanack</title><style>{CSS}</style></head><body><header><div class="wrap"><div class="brand"><a href="/star-almanack/">Star Almanack</a></div><div class="subtitle">Alexander Ferrari Miller</div></div></header><main class="wrap">{body}</main><footer><div class="wrap">© 2026 Alexander Ferrari Miller. All rights reserved.</div></footer></body></html>'''


def main() -> None:
    p = argparse.ArgumentParser(description="Rebuild clean Star Almanack week scaffolds")
    p.add_argument("start_year", type=int); p.add_argument("start_week", type=int)
    p.add_argument("end_year", type=int, nargs="?"); p.add_argument("end_week", type=int, nargs="?")
    a = p.parse_args()
    ey = a.end_year if a.end_year is not None else a.start_year
    ew = a.end_week if a.end_week is not None else a.start_week
    if (a.end_year is None) != (a.end_week is None):
        p.error("end_year and end_week must be supplied together")
    count = 0
    for year, week, monday in selected_weeks(a.start_year, a.start_week, ey, ew):
        out = PUBLIC_ROOT / str(year) / f"W{week:02d}"
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(page(year, week, monday), encoding="utf-8")
        count += 1
    print(f"Rebuilt {count} clean Almanack week scaffold(s).")


if __name__ == "__main__":
    main()
