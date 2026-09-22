#!/usr/bin/env python3
"""Create clean Star Almanack weekly page shells for an inclusive ISO-week range."""
from __future__ import annotations
import argparse
import datetime as dt
import html
from almanack_sections import section_open
from almanack_paths import ALMANACK_ROOT, typed_page, week_dir

BOTTOM_ID = "almanack-bottom-nav"
SCAFFOLD_PAGE_TYPES = ("calendar", "ephemeris", "planet-finder", "sky-notes")

CSS = r""":root{color-scheme:light dark;--ink:#202833;--muted:#66717d;--navy:#102a43;--link:#245c86;--paper:#fffdf8;--page:#eee9df;--rule:#d8d2c8}*{box-sizing:border-box}html{font-size:17px}body{margin:0;font-family:Georgia,'Times New Roman',serif;line-height:1.65;background:var(--page);color:var(--ink)}a,a:visited{color:var(--link)}header,footer{background:var(--navy);color:#fff}header{border-bottom:4px solid #c5a45c}header a,header a:visited,footer a,footer a:visited{color:#eef7ff}.wrap{max-width:1080px;margin:0 auto;padding:1.15rem 1.5rem}main.wrap{background:var(--paper);min-height:76vh;padding:2rem 2.4rem 3.25rem}.brand{font-size:1.35rem;font-weight:700}.subtitle{opacity:.86;font-size:.94rem}.weeknav,.yearnav{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:.8rem;margin:.4rem 0 1rem;font-family:system-ui,sans-serif;font-size:.9rem}.weeknav>:last-child,.yearnav>:last-child{justify-self:end}.weeknav a,.weeknav span,.yearnav a,.yearnav span{display:inline-block;min-width:5.5rem;padding:.58rem .8rem;border:1px solid #c8d3dc;border-radius:.45rem;text-decoration:none;text-align:center;background:#fff;color:var(--link)}.weeknav span[aria-current="page"],.yearnav span[aria-current="page"]{font-weight:700;background:var(--navy);color:#fff;border-color:var(--navy)}.nav-spacer{visibility:hidden}.almanack-bottom-nav-wrap{margin-top:2rem}h1,h2,h3{line-height:1.2;color:#17344d}h1{font-size:clamp(2rem,5vw,2.75rem)}h3{margin-top:2rem}table{width:100%;border-collapse:separate;border-spacing:0;margin:1rem 0 2rem;font-family:system-ui,sans-serif;font-size:.93rem;border:1px solid #cbd3da;border-radius:.5rem;overflow:hidden}th,td{padding:.7rem .8rem;border-right:1px solid #d6dde3;border-bottom:1px solid #d6dde3;vertical-align:top}th:last-child,td:last-child{border-right:0}tbody tr:last-child td{border-bottom:0}th{background:#e8f0f5;text-align:left;color:#17344d}.calendar{table-layout:fixed}.calendar th:first-child,.calendar td:first-child{width:28%}.calendar th:nth-child(2),.calendar td:nth-child(2){width:20%;text-align:center}.calendar th:nth-child(3),.calendar td:nth-child(3){width:52%}.ephemeris{display:table;table-layout:fixed;min-width:max-content;overflow:visible}.ephemeris-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}.ephemeris th,.ephemeris td{text-align:center;white-space:nowrap;min-width:6.5rem}.bayer-toggle-wrap{margin:.75rem 0;font-family:system-ui,sans-serif;overflow-x:auto;-webkit-overflow-scrolling:touch}.bayer-toggle{display:flex;align-items:center;justify-content:flex-end;gap:.35rem;flex-wrap:nowrap;min-width:max-content;font-size:.86rem}.bayer-toggle-label{margin-right:.2rem;color:var(--muted)}.bayer-toggle button{appearance:none;border:1px solid #c8d3dc;background:#fff;color:var(--link);padding:.35rem .62rem;border-radius:.4rem;font:inherit;cursor:pointer;white-space:nowrap}.bayer-toggle button[aria-pressed=true]{background:var(--navy);color:#fff;border-color:var(--navy)}.sky-note{border-left:3px solid #c8d3dc;padding-left:1rem}footer{font-family:system-ui,sans-serif;font-size:.88rem}@media(max-width:760px){html{font-size:16px}.wrap{padding-left:1rem;padding-right:1rem}main.wrap{padding:1.35rem 1rem 2.5rem}.weeknav,.yearnav{gap:.4rem}.weeknav a,.weeknav span,.yearnav a,.yearnav span{min-width:0;padding:.6rem .45rem}}@media(prefers-color-scheme:dark){:root{--ink:#dce6ef;--muted:#a7b4c0;--link:#9fd0ff;--paper:#17212b;--page:#10171f;--rule:#394957}h1,h2,h3{color:#f1f7fb}th{background:#223444;color:#eef7ff}th,td,table{border-color:#40505e}.weeknav a,.weeknav span,.yearnav a,.yearnav span,.bayer-toggle button{background:#1c2a36;border-color:#405567;color:#b6dcff}.weeknav span[aria-current="page"],.yearnav span[aria-current="page"],.bayer-toggle button[aria-pressed=true]{background:#eef7ff;color:#102a43;border-color:#eef7ff}}"""

def week_count(y): return dt.date(y,12,28).isocalendar().week

def validate(y,w):
    if y<1583 or y>9998: raise ValueError(f"unsupported Gregorian year: {y}")
    if w<1 or w>week_count(y): raise ValueError(f"ISO {y} has no week {w}")

def selected_weeks(sy,sw,ey,ew):
    validate(sy,sw); validate(ey,ew)
    d=dt.date.fromisocalendar(sy,sw,1); end=dt.date.fromisocalendar(ey,ew,1)
    if end<d: raise ValueError("end week precedes start week")
    while d<=end:
        y,w,_=d.isocalendar(); yield y,w,d; d+=dt.timedelta(days=7)

def published_years():
    if not ALMANACK_ROOT.exists(): return ()
    return tuple(sorted(int(p.name) for p in ALMANACK_ROOT.iterdir() if p.is_dir() and p.name.isdigit() and (p/'index.html').exists()))

def year_nav(year,bottom=False):
    ys=published_years(); previous=max((y for y in ys if y<year),default=None); following=min((y for y in ys if y>year),default=None); suffix=f'#{BOTTOM_ID}' if bottom else ''
    left=f'<a href="../../{previous}/{suffix}">← {previous}</a>' if previous else '<span class="nav-spacer" aria-hidden="true">—</span>'
    center=f'<a href="../{suffix}">{year}</a>'
    right=f'<a href="../../{following}/{suffix}">{following} →</a>' if following else '<span class="nav-spacer" aria-hidden="true">—</span>'
    return f'<nav class="yearnav">{left}{center}{right}</nav>'

def adjacent_week(year,week,days):
    t=(dt.date.fromisocalendar(year,week,1)+dt.timedelta(days=days)).isocalendar(); return t.year,t.week

def week_link(year,week,days,bottom=False):
    ty,tw=adjacent_week(year,week,days); href=f'../W{tw:02d}/' if ty==year else f'../../{ty}/W{tw:02d}/'; href += f'#{BOTTOM_ID}' if bottom else ''; label=f'ISO {ty}-W{tw:02d}'
    return f'<a href="{href}">← {label}</a>' if days<0 else f'<a href="{href}">{label} →</a>'

def week_nav(year,week,bottom=False):
    return '<nav class="weeknav week-position" aria-label="Week navigation">'+week_link(year,week,-7,bottom)+f'<span aria-current="page">ISO {year}-W{week:02d}</span>'+week_link(year,week,7,bottom)+'</nav>'

def site_nav(): return '<nav class="weeknav sitenav"><a href="/star-almanack/">Almanack Home</a><a href="/projects.html">All Projects</a><a href="/index.html">Main Site</a></nav>'
def nav_stack(y,w,bottom=False): return site_nav()+year_nav(y,bottom)+week_nav(y,w,bottom)

def notation_toggle(target):
    return (
        f'<div class="bayer-toggle-wrap section-notation-toggle" data-notation-target="{target}">'
        '<div class="bayer-toggle" role="group" aria-label="Astronomical notation">'
        '<span class="bayer-toggle-label">Notation:</span>'
        '<button type="button" data-bayer-mode="greek" aria-pressed="true">Greek/Symbols</button>'
        '<button type="button" data-bayer-mode="latin" aria-pressed="false">Latin</button>'
        '<button type="button" data-bayer-mode="mixed" data-legacy-label="Mixed · Learner" aria-pressed="false">Mixed Learner</button>'
        '</div></div>'
    )

def calendar_rows(monday):
    rows=[]
    for offset in range(7):
        d=monday+dt.timedelta(days=offset); label=f'{d.strftime("%a, %b")} {d.day}, {d.year}'; rows.append(f'<tr data-date="{d.isoformat()}"><td>{label}</td><td data-zodiac-day="">—</td><td data-events>—</td></tr>')
    return ''.join(rows)

def ephemeris_tables():
    primary=('Sun','Moon','Mercury','Venus','Mars','Jupiter','Saturn')
    extended=('Ceres','Uranus','Neptune','Pluto')
    def table(label,bodies):
        headers=''.join(f'<th>{body}</th>' for body in bodies)
        cells=''.join('<td>—</td>' for _ in bodies)
        return f'<h3>{label}</h3><div class="ephemeris-wrap"><table class="ephemeris"><thead><tr>{headers}</tr></thead><tbody><tr>{cells}</tr></tbody></table></div>'
    return table('Naked Eye Bodies',primary)+table('Extended Bodies',extended)

def page(year,week,monday,content_type=None):
    title=f'ISO {year}-W{week:02d}'; rows=calendar_rows(monday); top=nav_stack(year,week); bottom=f'<div class="almanack-bottom-nav-wrap" id="{BOTTOM_ID}">{nav_stack(year,week,True)}</div>'
    sections = {
        "calendar": f'{section_open(2)}{notation_toggle("calendar")}<h3>Calendar</h3><table class="calendar"><thead><tr><th>Date</th><th>Zodiac day</th><th>Events</th></tr></thead><tbody>{rows}</tbody></table></div>\n',
        "ephemeris": f'{section_open(3)}<h3>Weekly Solar-System Ephemeris</h3><p><strong>Snapshot:</strong> pending</p>{notation_toggle("ephemeris")}{ephemeris_tables()}</div>\n',
        "planet-finder": f'{section_open(4)}{notation_toggle("finder")}<h3>Planet Finder</h3><div class="planet-finder-block"><p>Planet finder pending.</p></div></div>\n',
        "sky-notes": f'{section_open(5)}<h3>Sky Notes</h3><div class="sky-note"><p>Sky notes pending.</p></div></div>',
    }
    if content_type is not None and content_type not in sections:
        raise ValueError(f"unsupported Almanack page type: {content_type}")
    content = ''.join(sections.values()) if content_type is None else sections[content_type]
    body=(
        f'{section_open(1)}{top}</div><h1>{title}</h1><p><strong>Week begins:</strong> {monday.strftime("Monday, %B")} {monday.day}, {monday.year}</p>\n'
        f'{content}{bottom}'
    )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · Star Almanack</title><style>{CSS}</style></head><body><header><div class="wrap"><div class="brand"><a href="/star-almanack/">Star Almanack</a></div><div class="subtitle">Alexander Ferrari Miller</div></div></header><main class="wrap">{body}</main><footer><div class="wrap">© 2026 Alexander Ferrari Miller. All rights reserved.</div></footer><script src="../../js/notation.js"></script></body></html>'''

def main():
    p=argparse.ArgumentParser(description='Rebuild clean Star Almanack week scaffolds'); p.add_argument('start_year',type=int); p.add_argument('start_week',type=int); p.add_argument('end_year',type=int,nargs='?'); p.add_argument('end_week',type=int,nargs='?'); a=p.parse_args(); ey=a.end_year if a.end_year is not None else a.start_year; ew=a.end_week if a.end_week is not None else a.start_week
    if (a.end_year is None)!=(a.end_week is None): p.error('end_year and end_week must be supplied together')
    count=0
    for year,week,monday in selected_weeks(a.start_year,a.start_week,ey,ew):
        rendered=page(year,week,monday)
        legacy = week_dir(year, week) / "index.html"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(rendered, encoding="utf-8")
        for content_type in SCAFFOLD_PAGE_TYPES:
            target = typed_page(year, week, content_type)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(page(year, week, monday, content_type), encoding="utf-8")
        count+=1
    print(f'Rebuilt {count} clean Almanack week scaffold(s).')

if __name__=='__main__': main()
