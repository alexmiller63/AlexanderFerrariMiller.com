#!/usr/bin/env python3
"""Build seasonal calendar pages from already-published weekly calendar rows.

Run after weekly publication: python tools/build_seasonal_calendar.py
The script deliberately refuses incomplete seasons or ambiguous ingress dates.
No ephemeris or Moon-name calculations are performed here.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
from pathlib import Path

from almanack_calendar import season_day_label

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "almanack"
DEST = SOURCE / "seasons"
SEASONS = (("spring", "Aries"), ("summer", "Cancer"),
           ("autumn", "Libra"), ("winter", "Capricorn"))
ROW = re.compile(r'<tr\b(?=[^>]*\bdata-date="(\d{4}-\d\d-\d\d)")[^>]*>.*?</tr>', re.S)
ZODIAC = re.compile(r'<td\b(?=[^>]*\bdata-zodiac-sign="([^"]+)")(?=[^>]*\bdata-zodiac-day="(\d+)")[^>]*>')
EVENT = re.compile(r'<div\b[^>]*class="[^"]*\bevent-cell\b[^"]*"[^>]*>.*?</div>', re.S)
PHASE = re.compile(r'New Moon|First Quarter|Full Moon|Last Quarter', re.I)
PLANET = re.compile(r'\b(?:Mercury|Venus|Mars|Jupiter|Saturn|Uranus|Neptune|Pluto)\b', re.I)
ASSET = re.compile(r'(?:src|href)="(?!https?:|/|#)([^"]+)"')
ZODIAC_ORDER = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]


def season_label(day: dt.date, sign: str, rows: dict) -> str:
    return season_day_label(day)


def source_rows() -> dict[dt.date, tuple[str, str, list[str]]]:
    found = {}
    files = sorted(SOURCE.glob("20??/W??/index.html"))
    if not files:
        raise ValueError("No published weekly calendar pages found")
    for file in files:
        page = file.read_text(encoding="utf-8")
        for row_match in ROW.finditer(page):
            iso = row_match.group(1)
            raw = row_match.group(0)
            day = dt.date.fromisoformat(iso)
            match = ZODIAC.search(raw)
            if not match:
                raise ValueError(f"Missing zodiac label: {file}: {iso}")
            sign, number = match.groups()
            events = EVENT.findall(raw)
            # The weekly source can contain repeated rows in adjacent ISO years.
            record = (sign, number, events)
            if day in found and found[day] != record:
                raise ValueError(f"Conflicting weekly records for {day}")
            found[day] = record
    return found


def ingress(rows: dict, sign: str, year: int) -> dt.date:
    candidates = [d for d, (s, n, _) in rows.items()
                  if d.year == year and s == sign and n == "1"]
    if len(candidates) != 1:
        raise ValueError(f"Expected one {sign} ingress in {year}; got {candidates}")
    return candidates[0]


def season_dates(rows: dict, year: int, index: int) -> tuple[dt.date, dt.date]:
    name, sign = SEASONS[index]
    start = ingress(rows, sign, year)
    next_year, next_index = (year + 1, 0) if index == 3 else (year, index + 1)
    stop = ingress(rows, SEASONS[next_index][1], next_year)
    if not 89 <= (stop - start).days <= 95:
        raise ValueError(f"Unexpected season length: {name} {year}: {stop-start}")
    return start, stop


def event_allowed(fragment: str) -> bool:
    plain = html.unescape(re.sub(r"<[^>]*>", " ", fragment))
    # Routine planetary entries are excluded; significant planetary events and lunar phases are retained.
    special = re.search(r"\b(opposition|greatest elongation|conjunction|greatest brilliance|maximum brightness|maximum brilliance|occultation|transit|retrograde|direct station|stationary)\b", plain, re.I)
    if PLANET.search(plain) and not special:
        return False
    if re.search(r'\bMoon\b', plain, re.I) and not (PHASE.search(plain) or re.search(r"eclipse|occultation", plain, re.I)):
        return False
    return True


def render(year: int, index: int, rows: dict) -> str:
    name, _ = SEASONS[index]
    start, stop = season_dates(rows, year, index)
    # Keep astronomical boundaries, but display every ISO week touching them.
    display_start = start - dt.timedelta(days=start.weekday())
    last = stop - dt.timedelta(days=1)
    display_stop = last + dt.timedelta(days=7-last.weekday())
    days = [display_start + dt.timedelta(days=i)
            for i in range((display_stop-display_start).days)]
    missing = [d for d in days if d not in rows]
    if missing:
        raise ValueError(f"Incomplete {name} {year}: {len(missing)} missing days, first {missing[0]}")
    # All dates in a season must span exactly its three consecutive zodiac signs.
    signs = list(dict.fromkeys(rows[d][0] for d in days if start <= d < stop))
    zodiac_order = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                    "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
    first = zodiac_order.index(SEASONS[index][1])
    required = [zodiac_order[(first+j)%12] for j in range(3)]
    if signs != required:
        raise ValueError(f"{name} {year}: expected {required}, found {signs}")
    title = f"{name.title()} {year}"
    prev = (year-1, 3) if index == 0 else (year, index-1)
    following = (year+1, 0) if index == 3 else (year, index+1)
    link = lambda p: f"/almanack/seasons/{p[0]}/{SEASONS[p[1]][0]}/"
    lines = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             f'<title>{title} · Star Almanack</title>',
             '<style>body{max-width:1050px;margin:auto;padding:1rem;font:17px/1.5 Georgia,serif;background:#fffdf8;color:#202833}nav{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}table{width:100%;border-collapse:collapse}th,td{border:1px solid #ccd4dc;padding:.55rem;vertical-align:top}th{background:#e8f0f5}td:first-child{white-space:nowrap}.event-cell{margin:.2rem 0}.zodiac-glyph{font-family:"Apple Symbols","Arial Unicode MS","Segoe UI Symbol","Noto Sans Symbols 2",serif;font-variant-emoji:text;color:inherit;-webkit-text-fill-color:currentColor}img{max-width:1.3em}a{color:#245c86}.week-link,.week-link:visited{display:block;margin:0 0 .35rem;padding:.72rem .55rem;border:1px solid #cbd3da;border-radius:.5rem;text-decoration:none;text-align:center;background:#fff;color:#245c86;font:650 .92rem/1.65 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}@media(max-width:600px){body{font-size:15px}th,td{padding:.3rem}td:first-child{white-space:normal}}</style>',
             '</head><body><header><a href="/star-almanack/">Star Almanack</a></header>',
             f'<h1>{title}</h1><p>{start:%B %d, %Y} – {(stop-dt.timedelta(days=1)):%B %d, %Y}</p>',
             f'<nav><a href="{link(prev)}">← Previous season</a><a href="/almanack/seasons/">All seasons</a><a href="{link(following)}">Next season →</a></nav>',
             '<p>Complete ISO weeks covering this season. Boundary weeks also appear in the adjoining season.</p>',
             '<div class="season-notation" role="group" aria-label="Astronomical notation"><span>Notation:</span> <button type="button" data-mode="greek" aria-pressed="true">Greek/Symbols</button> <button type="button" data-mode="latin" aria-pressed="false">Latin</button> <button type="button" data-mode="mixed" aria-pressed="false">Mixed Learner</button></div>',
             '<style>.season-notation{display:flex;align-items:center;flex-wrap:wrap;gap:.4rem;margin:1rem 0;font: .9rem system-ui,sans-serif}.season-notation button{border:1px solid #c8d3dc;border-radius:.4rem;padding:.4rem .6rem;background:white;color:#245c86;cursor:pointer}.season-notation button[aria-pressed=true]{background:#202f46;color:white}.zodiac-name{display:none}.season-notation[data-active=latin]~.iso-week .zodiac-glyph{display:none}.season-notation[data-active=latin]~.iso-week .zodiac-name{display:inline}.season-notation[data-active=mixed]~.iso-week .zodiac-name{display:inline}</style>',
             '<style>.iso-week{margin:1.5rem 0}.outside-season td{background:#f2f3f4}.season-marker{display:block;font:600 .8rem/1.4 system-ui,sans-serif}</style>']
    symbols = dict(zip(zodiac_order, "♈♉♊♋♌♍♎♏♐♑♒♓"))
    for day in days:
        sign, number, events = rows[day]
        cells = []
        for e in events:
            if not event_allowed(e):
                continue
            # Resolve relative asset links against the canonical site root.
            # Weekly pages and older nested pages use different relative depths.
            e = re.sub(r'(src|href)="(?:\.\./)+assets/', r'\1="/assets/', e)
            cells.append(e)
        date_label = f"{day:%a, %b %d, %Y}"
        if day.weekday() == 0:
            iso = day.isocalendar()
            lines.append(f'<section class="iso-week" aria-label="ISO {iso.year}-W{iso.week:02d}"><table><thead><tr><th>Date</th><th>Zodiac day</th><th>Events</th></tr></thead><tbody>')
            date_label = (f'<a class="week-link" href="/almanack/{iso.year}/W{iso.week:02d}/">'
                          f'ISO {iso.year}-W{iso.week:02d}</a>{date_label}')
        outside = not start <= day < stop
        row_class = ' class="outside-season"' if outside else ''
        season = season_label(day, sign, rows)
        lines.append(f'<tr data-date="{day.isoformat()}"{row_class}><td>{date_label}</td><td><span class="zodiac-glyph">{symbols[sign]}</span><span class="zodiac-name"> {sign}</span> {number}<span class="season-marker">{season}</span></td><td>{"".join(cells) or "—"}</td></tr>')
        if day.weekday() == 6:
            lines.append('</tbody></table></section>')
    lines.append('<script>document.querySelectorAll(".season-notation button").forEach(b=>b.addEventListener("click",()=>{const p=b.parentElement;p.dataset.active=b.dataset.mode;p.querySelectorAll("button").forEach(x=>x.setAttribute("aria-pressed",String(x===b)));}));</script>')
    lines.append('</body></html>')
    # Request monochrome text even on platforms that default zodiac to emoji.
    # Include glyphs copied from weekly event text; leave lunar emoji alone.
    return re.sub(r"([\u2648-\u2653])[\ufe0e\ufe0f]?", lambda m: m.group(1) + "\ufe0e", "\n".join(lines))


def main() -> None:
    rows = source_rows()
    plans = [(year, index) for year in range(2024, 2028)
             for index in range(4) if year != 2024 or index == 3]
    # All four seasons in 2025–2027 plus Winter 2024 = 13 pages.
    # Winter 2027 is already included in the 2027 four.
    if len(plans) != 13:
        raise AssertionError("Expected 13 seasons")
    generated = {(year, index): render(year, index, rows) for year, index in plans}
    for (year, index), page in generated.items():
        out = DEST / str(year) / SEASONS[index][0] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
    links = [f'<li><a href="/almanack/seasons/{year}/{SEASONS[index][0]}/">{SEASONS[index][0].title()} {year}</a></li>'
             for year, index in plans]
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Seasons · Star Almanack</title>'
        '<h1>Star Almanack · Seasons</h1><ul>' + "".join(links) + '</ul></html>', encoding="utf-8")
    print(f"Generated {len(generated)} complete seasonal calendars.")


if __name__ == "__main__":
    main()
