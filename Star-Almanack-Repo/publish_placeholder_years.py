#!/usr/bin/env python3
"""Publish polished placeholder ISO-week calendars for 2025 and 2027."""

from __future__ import annotations

import datetime as dt
import html
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
OUT_ROOT = ROOT / "site"
YEARS = (2025, 2027)

CSS = """
:root { color-scheme: light dark; --ink:#202833; --muted:#66717d; --navy:#102a43; --link:#245c86; --paper:#fffdf8; --page:#eee9df; --rule:#d8d2c8; --soft-blue:#edf4f8; }
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
.yearnav,.weeknav { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:.8rem; margin:.3rem 0 1.8rem; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:.9rem; }
.yearnav > :last-child,.weeknav > :last-child { justify-self:end; }
.yearnav a,.yearnav span,.weeknav a,.weeknav span { display:inline-block; min-width:5.5rem; padding:.5rem .75rem; border:1px solid #c8d3dc; border-radius:.45rem; text-decoration:none; background:#fff; color:var(--link); text-align:center; }
.yearnav span { font-weight:700; }
.weeknav span.disabled { color:var(--muted); }
h1,h2,h3 { line-height:1.2; color:#17344d; }
h1 { margin:.3rem 0 1rem; font-size:clamp(2rem,5vw,2.75rem); }
h2 { margin:2.25rem 0 .8rem; padding-bottom:.35rem; border-bottom:1px solid var(--rule); font-size:1.42rem; }
h3 { margin:1.5rem 0 .55rem; }
h2.month { margin:2rem 0 .65rem; font-size:1.28rem; }
h2.month .date { font-size:.82em; font-weight:400; color:var(--muted); margin-left:.4rem; }
p { max-width:72ch; margin:.7rem 0 1rem; }
.intro { max-width:72ch; }
.weekgrid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.7rem; padding:0; margin:.7rem 0 1.5rem; list-style:none; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
.weekgrid a { display:block; padding:.85rem .9rem; border:1px solid #cbd3da; border-radius:.5rem; text-decoration:none; background:#fff; color:var(--link); }
.week { font-weight:700; }
.coming { display:block; margin-top:.25rem; color:var(--muted); font-size:.88rem; }
.placeholder { border:1px solid var(--rule); border-radius:.6rem; padding:1.5rem; background:var(--paper); }
.placeholder-note { color:var(--muted); }
table { width:100%; border-collapse:separate; border-spacing:0; margin:1rem 0 2rem; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:.93rem; line-height:1.45; border:1px solid #cbd3da; border-radius:.5rem; overflow:hidden; }
th,td { padding:.7rem .8rem; vertical-align:top; border-right:1px solid #d6dde3; border-bottom:1px solid #d6dde3; }
th:last-child,td:last-child { border-right:0; }
tbody tr:last-child td { border-bottom:0; }
th { background:#e8f0f5; text-align:left; color:#17344d; font-weight:700; }
tbody tr:nth-child(even) td { background:#fbfaf7; }
table.calendar { table-layout:fixed; }
table.calendar th:first-child,table.calendar td:first-child { width:28%; }
table.calendar th:nth-child(2),table.calendar td:nth-child(2) { width:20%; text-align:center; }
table.calendar th:nth-child(3),table.calendar td:nth-child(3) { width:52%; }
table.ephemeris th,table.ephemeris td { text-align:center; white-space:nowrap; }
.finder-controls { display:flex; justify-content:center; gap:.35rem; flex-wrap:wrap; margin:.8rem 0 1rem; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
.finder-controls button { appearance:none; border:1px solid #c8d3dc; background:#fff; color:var(--link); padding:.42rem .7rem; border-radius:.42rem; font:inherit; cursor:pointer; }
.finder-controls button[aria-pressed="true"] { background:var(--navy); color:#fff; border-color:var(--navy); }
.finder { max-width:720px; margin:0 auto 2rem; border:1px solid var(--rule); border-radius:.55rem; padding:.8rem; background:var(--paper); }
.finder svg { display:block; width:100%; height:auto; }
.finder figcaption { text-align:center; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:.82rem; color:var(--muted); margin-top:.35rem; }
.finder [data-mode] { display:none; }
.finder [data-mode="greek"] { display:inline; }
.sky-note { border-left:3px solid #c8d3dc; padding-left:1rem; }
footer { font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:.88rem; }
footer .wrap { padding-top:1.3rem; padding-bottom:1.3rem; opacity:.9; }
@media (max-width:760px) { html{font-size:16px}.wrap{padding-left:1rem;padding-right:1rem}main.wrap{padding:1.35rem 1rem 2.5rem;box-shadow:none}.weekgrid{grid-template-columns:repeat(2,minmax(0,1fr));gap:.55rem}.weekgrid a{padding:.72rem .55rem;font-size:.92rem}h2.month .date{display:block;margin-left:0;margin-top:.15rem}table.ephemeris{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}.yearnav,.weeknav{gap:.4rem}.yearnav a,.yearnav span,.weeknav a,.weeknav span{min-width:0;padding:.5rem .45rem} }
@media (prefers-color-scheme:dark) { :root{--ink:#dce6ef;--muted:#a7b4c0;--link:#9fd0ff;--paper:#17212b;--page:#10171f;--rule:#394957} body{background:var(--page);color:var(--ink)} main.wrap{background:var(--paper);box-shadow:none} h1,h2,h3{color:#f1f7fb} .yearnav a,.yearnav span,.weeknav a,.weeknav span,.weekgrid a,.finder-controls button{background:#1c2a36;border-color:#405567;color:#b6dcff} .weeknav span.disabled{color:#7f909f}.finder-controls button[aria-pressed="true"]{background:#eef7ff;color:#102a43;border-color:#eef7ff} th{background:#223444;color:#eef7ff}th,td,table{border-color:#40505e}tbody tr:nth-child(even) td{background:#1b2732} }
""".strip()

SCRIPT = """
<script>
document.addEventListener('click', function (e) {
  const button = e.target.closest('[data-finder-mode]');
  if (!button) return;
  const wrap = button.closest('.planet-finder-block');
  const mode = button.dataset.finderMode;
  wrap.querySelectorAll('[data-finder-mode]').forEach(b => b.setAttribute('aria-pressed', b === button ? 'true' : 'false'));
  wrap.querySelectorAll('.finder [data-mode]').forEach(g => g.style.display = g.dataset.mode === mode ? 'inline' : 'none');
  const caption = wrap.querySelector('figcaption');
  caption.textContent = button.textContent;
});
</script>
""".strip()


def shell(title: str, body: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · Star Almanack</title><style>{CSS}</style></head><body><header><div class="wrap"><div class="brand"><a href="../2026/">Star Almanack</a></div><div class="subtitle">Alexander Ferrari Miller</div></div></header><main class="wrap">{body}</main><footer><div class="wrap">© 2026 Alexander Ferrari Miller. All rights reserved.</div></footer>{SCRIPT}</body></html>'''


def year_nav(year: int) -> str:
    if year == 2025:
        return '<nav class="yearnav"><span></span><span>ISO 2025</span><a href="../2026/">2026 →</a></nav>'
    return '<nav class="yearnav"><a href="../2026/">← 2026</a><span>ISO 2027</span><span></span></nav>'


def week_count(year: int) -> int:
    return dt.date(year, 12, 28).isocalendar().week


def week_nav(year: int, week: int) -> str:
    count = week_count(year)
    if week > 1:
        prev = f'<a href="../W{week-1:02d}/">← W{week-1:02d}</a>'
    elif year == 2027:
        prev = '<a href="../../2026/W53/">← 2026-W53</a>'
    else:
        prev = '<span class="disabled">← Previous</span>'

    if week < count:
        nxt = f'<a href="../W{week+1:02d}/">W{week+1:02d} →</a>'
    elif year == 2025:
        nxt = '<a href="../../2026/W01/">2026-W01 →</a>'
    else:
        nxt = '<span class="disabled">Next →</span>'

    return f'<nav class="weeknav">{prev}<a href="../">All {year} weeks</a>{nxt}</nav>'


def empty_finder_svg() -> str:
    symbols = ["♈︎","♉︎","♊︎","♋︎","♌︎","♍︎","♎︎","♏︎","♐︎","♑︎","♒︎","♓︎"]
    latin = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
    positions = [(22,100),(32,60),(58,32),(100,22),(142,32),(168,60),(178,100),(168,140),(142,168),(100,178),(58,168),(32,140)]
    greek_labels = ''.join(f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="middle" font-family="Georgia,Times New Roman,serif" font-size="12" fill="#111">{s}</text>' for s,(x,y) in zip(symbols,positions))
    latin_labels = ''.join(f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="middle" font-family="Arial,Helvetica,sans-serif" font-size="5.2" fill="#111">{s}</text>' for s,(x,y) in zip(latin,positions))
    mixed_labels = ''.join(f'<text x="{x}" y="{y-2}" text-anchor="middle" dominant-baseline="middle" font-family="Georgia,Times New Roman,serif" font-size="10" fill="#111">{sym}</text><text x="{x}" y="{y+6}" text-anchor="middle" dominant-baseline="middle" font-family="Arial,Helvetica,sans-serif" font-size="4.2" fill="#111">{name}</text>' for sym,name,(x,y) in zip(symbols,latin,positions))
    spokes=''.join(f'<line x1="100" y1="100" x2="{x}" y2="{y}" stroke="#111" stroke-opacity=".28" stroke-width="1"/>' for x,y in positions)
    return f'''<svg viewBox="0 0 200 200" role="img" aria-label="Empty planet finder"><rect width="200" height="200" fill="white"/><circle cx="100" cy="100" r="78" fill="none" stroke="#111" stroke-width="1.5"/>{spokes}<g data-mode="greek">{greek_labels}</g><g data-mode="latin">{latin_labels}</g><g data-mode="mixed">{mixed_labels}</g><circle cx="100" cy="100" r="3" fill="none" stroke="#111"/><text x="100" y="96" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="7" fill="#111">Tropical ecliptic longitude</text><text x="100" y="105" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="5.5" fill="#555">planet positions pending</text></svg>'''


def weekly_placeholder(year: int, week: int, monday: dt.date) -> str:
    dates=[monday+dt.timedelta(days=i) for i in range(7)]
    rows=''.join(f'<tr><td>{d.strftime("%a, %b %-d, %Y")}</td><td>—</td><td>—</td></tr>' for d in dates)
    calendar=f'''<h3>Calendar</h3><table class="calendar"><thead><tr><th>Date</th><th>Zodiac day</th><th>Events</th></tr></thead><tbody>{rows}</tbody></table>'''
    ephemeris='''<h3>Weekly Solar-System Ephemeris</h3><p><strong>Snapshot:</strong> pending</p><table class="ephemeris"><thead><tr><th>Sun</th><th>Moon</th><th>Mercury</th><th>Venus</th><th>Mars</th><th>Jupiter</th><th>Saturn</th></tr></thead><tbody><tr><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td></tr></tbody></table><p><strong>Extended targets:</strong></p><table class="ephemeris"><thead><tr><th>Uranus</th><th>Neptune</th><th>Ceres</th></tr></thead><tbody><tr><td>—</td><td>—</td><td>—</td></tr></tbody></table>'''
    finders=f'''<h3>Planet Finder</h3><div class="planet-finder-block"><div class="finder-controls" role="group" aria-label="Planet finder notation"><button type="button" data-finder-mode="greek" aria-pressed="true">Greek / Symbols</button><button type="button" data-finder-mode="latin" aria-pressed="false">Latin</button><button type="button" data-finder-mode="mixed" aria-pressed="false">Mixed Learner</button></div><figure class="finder">{empty_finder_svg()}<figcaption>Greek / Symbols</figcaption></figure></div>'''
    lorem='Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    sky=f'''<h3>Sky Notes</h3><div class="sky-note"><h4>Naked eye</h4><p>{lorem}</p><h4>Binoculars</h4><p>{lorem}</p><h4>Telescope</h4><p>{lorem}</p></div>'''
    return calendar+ephemeris+finders+sky


def build_year(year: int) -> None:
    out = OUT_ROOT / str(year)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    weeks=[(w, dt.date.fromisocalendar(year, w, 1)) for w in range(1, week_count(year)+1)]

    for week,monday in weeks:
        page=out / f'W{week:02d}'
        page.mkdir()
        title=f'ISO week {week:02d} {year}'
        body=(year_nav(year)
              + week_nav(year,week)
              + '<section class="placeholder">'
              + f'<h1>{title}</h1>'
              + '<p class="placeholder-note">This week is currently in preparation and will be published as part of the Star Almanack.</p>'
              + f'<p><strong>Week begins:</strong> {monday.strftime("Monday, %B %-d, %Y")}</p>'
              + '</section>'
              + weekly_placeholder(year,week,monday)
              + week_nav(year,week)
              + year_nav(year))
        (page/'index.html').write_text(shell(title,body),encoding='utf-8')

    groups=[]
    current_key=None
    current=[]
    for week,monday in weeks:
        key=(monday.year,monday.month)
        if current_key is not None and key != current_key:
            groups.append((current_key,current))
            current=[]
        current_key=key
        current.append((week,monday))
    if current:
        groups.append((current_key,current))

    rendered=[]
    for (_, _),items in groups:
        first_monday=items[0][1]
        links=''.join(
            f'<li><a href="W{week:02d}/"><span class="week">ISO week {week:02d} {year}</span><span class="coming">coming soon</span></a></li>'
            for week,_ in items
        )
        rendered.append(
            f'<h2 class="month">{first_monday.strftime("%B %Y")} '
            f'<span class="date">{first_monday.strftime("%B %-d, %Y")}</span></h2>'
            f'<ul class="weekgrid">{links}</ul>'
        )

    body=(year_nav(year)
          + f'<h1>{year} Weekly Almanack</h1>'
          + f'<p class="intro">The {year} edition is in preparation. The calendar below shows the complete ISO week-year, grouped by the civil month containing each week’s Monday. Each week will be replaced by the completed Almanack entry as it is published.</p>'
          + ''.join(rendered)
          + year_nav(year))
    (out/'index.html').write_text(shell(f'{year} Weekly Almanack',body),encoding='utf-8')


def main() -> None:
    for year in YEARS:
        build_year(year)
    print('Published enriched placeholder ISO-week calendars for 2025 and 2027')


if __name__ == '__main__':
    main()
