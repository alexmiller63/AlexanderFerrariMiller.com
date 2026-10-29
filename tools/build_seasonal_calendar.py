#!/usr/bin/env python3
"""Build seasonal calendar pages from already-published weekly calendar rows.

Run after weekly publication: python tools/build_seasonal_calendar.py
The script deliberately refuses incomplete seasons or ambiguous ingress dates.
No ephemeris or Moon-name calculations are performed here.
"""
from __future__ import annotations

import datetime as dt
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "almanack"
DEST = SOURCE / "seasons"
SEASONS = (("spring", "Aries"), ("summer", "Cancer"),
           ("autumn", "Libra"), ("winter", "Capricorn"))
ROW = re.compile(r'<tr data-date="(\d{4}-\d\d-\d\d)".*?</tr>', re.S)
ZODIAC = re.compile(r'<td data-zodiac-sign="([^"]+)" data-zodiac-day="(\d+)"')
EVENT = re.compile(r'<div class="event-cell"[^>]*>.*?</div>', re.S)
PHASE = re.compile(r'New Moon|First Quarter|Full Moon|Last Quarter', re.I)
PLANET = re.compile(r'\b(?:Mercury|Venus|Mars|Jupiter|Saturn|Uranus|Neptune|Pluto)\b', re.I)
ASSET = re.compile(r'(?:src|href)="(?!https?:|/|#)([^"]+)"')


def source_rows() -> dict[dt.date, tuple[str, str, list[str]]]:
    found = {}
    for file in sorted(SOURCE.glob("20??/W??/calendar/index.html")):
        page = file.read_text(encoding="utf-8")
        for iso, raw in ROW.findall(page):
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
    # Planetary entries are excluded; lunar phase entries are retained.
    if PLANET.search(plain):
        return False
    if re.search(r'\bMoon\b', plain, re.I) and not PHASE.search(plain):
        return False
    return True


def render(year: int, index: int, rows: dict) -> str:
    name, _ = SEASONS[index]
    start, stop = season_dates(rows, year, index)
    days = [start + dt.timedelta(days=i) for i in range((stop-start).days)]
    missing = [d for d in days if d not in rows]
    if missing:
        raise ValueError(f"Incomplete {name} {year}: {len(missing)} missing days, first {missing[0]}")
    # All dates in a season must span exactly its three consecutive zodiac signs.
    expected = [SEASONS[index][1],
                list(SEASONS[k][1] for k in range(4))[index] if False else None]
    signs = list(dict.fromkeys(rows[d][0] for d in days))
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
             '<style>body{max-width:1050px;margin:auto;padding:1rem;font:17px/1.5 Georgia,serif;background:#fffdf8;color:#202833}nav{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}table{width:100%;border-collapse:collapse}th,td{border:1px solid #ccd4dc;padding:.55rem;vertical-align:top}th{background:#e8f0f5}td:first-child{white-space:nowrap}.event-cell{margin:.2rem 0}img{max-width:1.3em}a{color:#245c86}@media(max-width:600px){body{font-size:15px}th,td{padding:.3rem}td:first-child{white-space:normal}}</style>',
             '</head><body><header><a href="/star-almanack/">Star Almanack</a></header>',
             f'<h1>{title}</h1><p>{start:%B %d, %Y} – {(stop-dt.timedelta(days=1)):%B %d, %Y}</p>',
             f'<nav><a href="{link(prev)}">← Previous season</a><a href="/almanack/seasons/">All seasons</a><a href="{link(following)}">Next season →</a></nav>',
             '<table><thead><tr><th>Date</th><th>Zodiac day</th><th>Events</th></tr></thead><tbody>']
    symbols = dict(zip(zodiac_order, "♈♉♊♋♌♍♎♏♐♑♒♓"))
    for day in days:
        sign, number, events = rows[day]
        cells = []
        for e in events:
            if not event_allowed(e):
                continue
            # Resolve relative asset links against the canonical site root.
            e = ASSET.sub(lambda m: m.group(0).replace(m.group(1), "/almanack/assets/" + m.group(1))
                          if False else m.group(0), e)
            # The source uses paths relative to /almanack/YYYY/Www/calendar/.
            e = re.sub(r'(src|href)="(?:\.\./){4}assets/', r'\1="/assets/', e)
            cells.append(e)
        lines.append(f'<tr data-date="{day.isoformat()}"><td>{day:%a, %b %d, %Y}</td><td>{symbols[sign]} {number}</td><td>{"".join(cells) or "—"}</td></tr>')
    lines.append('</tbody></table></body></html>')
    return "\n".join(lines)


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
