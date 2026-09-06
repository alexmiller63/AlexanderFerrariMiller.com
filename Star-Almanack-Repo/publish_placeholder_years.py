#!/usr/bin/env python3
"""Publish placeholder ISO-week calendars for 2025 and 2027.

These are deliberately lightweight companion layers around the complete 2026
Almanack. They show the ISO week-year structure and make the civil-date
boundaries visible without pretending that the detailed weekly content exists.
"""

from __future__ import annotations

import datetime as dt
import html
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
OUT_ROOT = ROOT / "site"
YEARS = (2025, 2027)

CSS = """
:root { color-scheme: light dark; --ink:#202833; --muted:#66717d; --navy:#102a43; --link:#245c86; --paper:#fffdf8; --page:#eee9df; --rule:#d8d2c8; }
* { box-sizing:border-box; }
html { font-size:17px; }
body { margin:0; font-family:Georgia,'Times New Roman',serif; line-height:1.65; background:var(--page); color:var(--ink); -webkit-font-smoothing:antialiased; }
a,a:visited { color:var(--link); text-underline-offset:.15em; }
header,footer { background:var(--navy); color:#fff; }
header { border-bottom:4px solid #c5a45c; }
header a,header a:visited,footer a,footer a:visited { color:#eef7ff; }
.wrap { max-width:1080px; margin:0 auto; padding:1.15rem 1.5rem; }
main.wrap { background:var(--paper); min-height:76vh; padding:2rem 2.4rem 3.25rem; box-shadow:0 0 28px rgba(25,35,45,.08); }
.brand { font-size:1.35rem; font-weight:700; }
.subtitle { margin-top:.1rem; opacity:.86; font-size:.94rem; }
.yearnav { display:flex; gap:.6rem; flex-wrap:wrap; margin:.3rem 0 1.8rem; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:.9rem; }
.yearnav a,.yearnav span { padding:.5rem .75rem; border:1px solid #c8d3dc; border-radius:.45rem; text-decoration:none; background:#fff; }
h1,h2 { line-height:1.2; color:#17344d; }
h1 { margin:.3rem 0 1rem; font-size:clamp(2rem,5vw,2.75rem); }
h2.month { margin:2rem 0 .65rem; padding-bottom:.35rem; border-bottom:1px solid var(--rule); font-size:1.28rem; }
h2.month .date { font-size:.82em; font-weight:400; color:var(--muted); margin-left:.4rem; }
.intro { max-width:72ch; }
.weekgrid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.7rem; padding:0; margin:.7rem 0 1.5rem; list-style:none; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
.weekgrid a { display:block; padding:.85rem .9rem; border:1px solid #cbd3da; border-radius:.5rem; text-decoration:none; background:#fff; color:var(--link); }
.week { font-weight:700; }
.coming { display:block; margin-top:.25rem; color:var(--muted); font-size:.88rem; }
footer { font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:.88rem; }
footer .wrap { padding-top:1.3rem; padding-bottom:1.3rem; opacity:.9; }
@media (max-width:760px) { html{font-size:16px} .wrap{padding-left:1rem;padding-right:1rem} main.wrap{padding:1.35rem 1rem 2.5rem;box-shadow:none} .weekgrid{grid-template-columns:repeat(2,minmax(0,1fr));gap:.55rem} .weekgrid a{padding:.72rem .55rem;font-size:.92rem} h2.month .date{display:block;margin-left:0;margin-top:.15rem} }
@media (prefers-color-scheme:dark) { :root{--ink:#dce6ef;--muted:#a7b4c0;--link:#9fd0ff;--paper:#17212b;--page:#10171f;--rule:#394957} body{background:var(--page);color:var(--ink)} main.wrap{background:var(--paper);box-shadow:none} h1,h2{color:#f1f7fb} .yearnav a,.yearnav span,.weekgrid a{background:#1c2a36;border-color:#405567;color:#b6dcff} }
""".strip()


def shell(title: str, body: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · Star Almanack</title><style>{CSS}</style></head><body><header><div class="wrap"><div class="brand"><a href="/almanack/2026/">Star Almanack</a></div><div class="subtitle">Alexander Ferrari Miller</div></div></header><main class="wrap">{body}</main><footer><div class="wrap">© {title.split()[0]} Alexander Ferrari Miller. All rights reserved.</div></footer></body></html>'''


def year_nav(year: int) -> str:
    links=[]
    for y in (2025, 2026, 2027):
        if y == year:
            links.append(f'<span>{y}</span>')
        else:
            links.append(f'<a href="/almanack/{y}/">{y}</a>')
    return '<nav class="yearnav">' + ''.join(links) + '</nav>'


def build_year(year: int) -> None:
    out = OUT_ROOT / str(year)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    weeks=[]
    for week in range(1, 54):
        try:
            monday=dt.date.fromisocalendar(year, week, 1)
        except ValueError:
            break
        weeks.append((week,monday))
        page=out / f'W{week:02d}'
        page.mkdir()
        title=f'ISO week {week} {year}'
        body=(year_nav(year)
              + f'<h1>{html.escape(title)}</h1>'
              + f'<p class="intro"><strong>{html.escape(title)} coming soon.</strong> This weekly Almanack installment is currently in preparation and will be published as part of the Star Almanack.</p>'
              + f'<p>ISO week: {year}-W{week:02d}<br>Week begins: {monday.strftime("%A, %B %-d, %Y")}</p>')
        (page/'index.html').write_text(shell(title,body),encoding='utf-8')

    month_groups={}
    for week,monday in weeks:
        month_groups.setdefault(monday.month,[]).append((week,monday))

    groups=[]
    # W01 can begin in December of the preceding civil year.
    first_week=weeks[0]
    if first_week[1].year < year:
        week,monday=first_week
        groups.append(f'<h2 class="month">{monday.strftime("%B %Y")} <span class="date">{monday.strftime("%B %-d, %Y")}</span></h2><ul class="weekgrid"><li><a href="W{week:02d}/"><span class="week">ISO week {week} {year}</span><span class="coming">{year}-W{week:02d} coming soon</span></a></li></ul>')

    for month in range(1,13):
        items=month_groups.get(month,[])
        if not items:
            continue
        monday=items[0][1]
        links=''.join(f'<li><a href="W{week:02d}/"><span class="week">ISO week {week} {year}</span><span class="coming">{year}-W{week:02d} coming soon</span></a></li>' for week,_ in items)
        groups.append(f'<h2 class="month">{monday.strftime("%B %Y")} <span class="date">{monday.strftime("%B %-d, %Y")}</span></h2><ul class="weekgrid">{links}</ul>')

    body=year_nav(year)+f'<h1>{year} Weekly Almanack</h1><p class="intro">The {year} edition is in preparation. The calendar below shows the complete ISO week-year structure and its civil-date boundaries. Detailed weekly Almanack content is coming soon.</p>'+''.join(groups)
    (out/'index.html').write_text(shell(f'{year} Weekly Almanack',body),encoding='utf-8')


def main() -> None:
    for year in YEARS:
        build_year(year)
    print('Published placeholder ISO-week calendars for 2025 and 2027')


if __name__ == '__main__':
    main()
