#!/usr/bin/env python3
"""Populate Star Almanack calendar astronomy for one or more ISO years.

Year-independent engine using JPL Horizons apparent geocentric ecliptic-of-date
longitudes for the Sun and Moon. Event times are linearly interpolated between
1-hour samples and written to both source and public Almanack trees.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Star-Almanack-Repo" / "site"
PUBLIC_ROOT = ROOT / "almanack"
DATA_ROOT = ROOT / "Star-Almanack-Repo" / "generated"
SIGNS = "♈♉♊♋♌♍♎♏♐♑♒♓"
SIGN_NAMES = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)
PHASES = ((0.0, "🌑 New Moon"), (90.0, "🌓 First Quarter"),
          (180.0, "🌕 Full Moon"), (270.0, "🌗 Last Quarter"))
WHEEL_STATIONS = (
    (315.0, "Winter–Spring midpoint", "Imbolc"),
    (0.0, "March equinox", "Ostara"),
    (45.0, "Spring–Summer midpoint", "Beltane"),
    (90.0, "June solstice", "Litha"),
    (135.0, "Summer–Autumn midpoint", "Lughnasadh"),
    (180.0, "September equinox", "Mabon"),
    (225.0, "Autumn–Winter midpoint", "Samhain"),
    (270.0, "December solstice", "Yule"),
)
HORIZONS_API = "https://ssd.jpl.nasa.gov/api/horizons.api"


def iso_bounds(year: int) -> tuple[date, date]:
    first = date.fromisocalendar(year, 1, 1)
    weeks = date(year, 12, 28).isocalendar().week
    return first, date.fromisocalendar(year, weeks, 7)


def jd_to_datetime(jd: float) -> datetime:
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(days=jd - 2440587.5)


def horizons_longitudes(command: str, start: date, stop: date) -> list[tuple[datetime, float]]:
    params = {
        "format": "json", "COMMAND": f"'{command}'", "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'OBSERVER'", "CENTER": "'500@399'",
        "START_TIME": f"'{start.isoformat()} 00:00'", "STOP_TIME": f"'{stop.isoformat()} 00:00'",
        "STEP_SIZE": "'1 h'", "QUANTITIES": "'31'", "CSV_FORMAT": "'YES'",
        "ANG_FORMAT": "'DEG'", "CAL_FORMAT": "'JD'", "TIME_DIGITS": "'SECONDS'",
    }
    url = HORIZONS_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Star-Almanack/calendar-population"})
    with urllib.request.urlopen(req, timeout=120) as response:
        payload = json.load(response)
    text = payload.get("result", "")
    if "$$SOE" not in text or "$$EOE" not in text:
        raise RuntimeError(f"Horizons returned no ephemeris for target {command}: {text[:500]}")
    lines = text.splitlines()
    header_line = next((line for line in lines if "ObsEcLon" in line), None)
    if not header_line:
        raise RuntimeError(f"Could not find ObsEcLon header for target {command}")
    header = [h.strip() for h in next(csv.reader([header_line]))]
    lon_index = header.index("ObsEcLon")
    start_i, stop_i = lines.index("$$SOE") + 1, lines.index("$$EOE")
    out = []
    for line in lines[start_i:stop_i]:
        if line.strip():
            row = next(csv.reader([line]))
            out.append((jd_to_datetime(float(row[0].strip())), float(row[lon_index].strip()) % 360.0))
    return out


def unwrap(values: list[float]) -> list[float]:
    if not values: return []
    out = [values[0]]
    for raw in values[1:]:
        prev, candidate = out[-1], raw
        while candidate - prev > 180.0: candidate -= 360.0
        while candidate - prev < -180.0: candidate += 360.0
        out.append(candidate)
    return out


def interpolate_time(t0: datetime, v0: float, t1: datetime, v1: float, target: float) -> datetime:
    if v1 == v0: return t0
    f = min(1.0, max(0.0, (target - v0) / (v1 - v0)))
    return t0 + (t1 - t0) * f


def longitude_events(samples: list[tuple[datetime, float]], step: float) -> list[tuple[datetime, float]]:
    times = [t for t, _ in samples]; u = unwrap([x for _, x in samples]); events = []
    lo, hi, j = int(u[0] // step) - 1, int(u[-1] // step) + 1, 0
    for k in range(lo, hi + 1):
        target = step * k
        while j + 1 < len(u) and u[j + 1] < target: j += 1
        if j + 1 >= len(u): break
        if u[j] <= target <= u[j + 1]:
            events.append((interpolate_time(times[j], u[j], times[j + 1], u[j + 1], target), target % 360.0))
    return events


def solar_ingresses(samples):
    return [(ts, int(round(lon / 30.0)) % 12) for ts, lon in longitude_events(samples, 30.0)]


def wheel_of_year(samples):
    metadata = {lon: (astronomical, traditional) for lon, astronomical, traditional in WHEEL_STATIONS}
    events = []
    for ts, lon in longitude_events(samples, 45.0):
        key = round(lon) % 360; astronomical, traditional = metadata[float(key)]
        events.append((ts, float(key), astronomical, traditional))
    return events


def lunar_phases(sun, moon):
    if len(sun) != len(moon): raise RuntimeError("Sun and Moon sample counts differ")
    times = [t for t, _ in sun]
    elong = unwrap([((m - s) % 360.0) for (_, s), (_, m) in zip(sun, moon)])
    events = []; lo, hi, j = int(elong[0] // 90) - 1, int(elong[-1] // 90) + 1, 0
    for k in range(lo, hi + 1):
        target = 90.0 * k
        while j + 1 < len(elong) and elong[j + 1] < target: j += 1
        if j + 1 >= len(elong): break
        if elong[j] <= target <= elong[j + 1]:
            events.append((interpolate_time(times[j], elong[j], times[j + 1], elong[j + 1], target), PHASES[k % 4][1]))
    return events


def zodiac_for_day(d, ingresses):
    eligible = [(ts.date(), idx) for ts, idx in ingresses if ts.date() <= d]
    if not eligible: raise RuntimeError(f"No preceding ingress available for {d}")
    ingress_day, idx = eligible[-1]
    return idx, (d - ingress_day).days + 1


def zodiac_label(d, ingresses):
    idx, n = zodiac_for_day(d, ingresses); glyph = f'<span class="zodiac-glyph">{SIGNS[idx]}</span>'
    return f"{glyph} {n}"


def fmt_utc(ts): return ts.astimezone(timezone.utc).strftime("%H:%M:%S UTC")


def build_events(first, last, ingresses, phases, wheel):
    events = {}
    for ts, idx in ingresses:
        if first <= ts.date() <= last:
            deg = idx * 30; glyph = f'<span class="zodiac-glyph">{SIGNS[idx]}</span>'
            events.setdefault(ts.date(), []).append(f"{glyph} {SIGN_NAMES[idx]} ingress ({deg}°) — {fmt_utc(ts)}")
    for ts, lon, astronomical, traditional in wheel:
        if first <= ts.date() <= last:
            events.setdefault(ts.date(), []).append(f"Wheel of the Year: {traditional} — {astronomical} ({int(lon)}°) — {fmt_utc(ts)}")
    for ts, label in phases:
        if first <= ts.date() <= last: events.setdefault(ts.date(), []).append(f"{label} — {fmt_utc(ts)}")
    return events


ROW_RE = re.compile(r"<tr><td>((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), [^<]+)</td><td>.*?</td><td>(.*?)</td></tr>")


def parse_page_date(label): return datetime.strptime(label, "%a, %b %d, %Y").date()


def patch_page(path, ingresses, events):
    if not path.exists(): return False
    text = path.read_text(encoding="utf-8")
    def repl(match):
        label = match.group(1); d = parse_page_date(label); z = zodiac_label(d, ingresses)
        existing = [x for x in match.group(2).split("<br>") if x and x != "—"]
        generated = events.get(d, [])
        keep = [x for x in existing if " ingress (" not in x and not x.startswith("Wheel of the Year:") and not x.startswith(("🌑 New Moon", "🌓 First Quarter", "🌕 Full Moon", "🌗 Last Quarter"))]
        merged = keep + generated
        return f"<tr><td>{label}</td><td>{z}</td><td>{'<br>'.join(merged) if merged else '—'}</td></tr>"
    new = ROW_RE.sub(repl, text)
    if new != text:
        path.write_text(new, encoding="utf-8"); return True
    return False


def write_data(year, ingresses, phases, wheel):
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "year": year,
        "basis": "JPL Horizons apparent geocentric ecliptic-of-date longitude; 1-hour sampling with linear interpolation",
        "solar_ingresses": [{"utc": ts.isoformat().replace("+00:00", "Z"), "sign": SIGNS[idx], "name": SIGN_NAMES[idx], "longitude_deg": idx * 30} for ts, idx in ingresses],
        "wheel_of_the_year": [{"utc": ts.isoformat().replace("+00:00", "Z"), "longitude_deg": int(lon), "astronomical_name": astronomical, "traditional_name": traditional} for ts, lon, astronomical, traditional in wheel],
        "lunar_phases": [{"utc": ts.isoformat().replace("+00:00", "Z"), "phase": label} for ts, label in phases],
    }
    (DATA_ROOT / f"calendar-{year}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def populate_year(year):
    first, last = iso_bounds(year); query_start, query_stop = first - timedelta(days=45), last + timedelta(days=45)
    sun = horizons_longitudes("10", query_start, query_stop); moon = horizons_longitudes("301", query_start, query_stop)
    ingresses = solar_ingresses(sun); wheel = wheel_of_year(sun); phases = lunar_phases(sun, moon)
    events = build_events(first, last, ingresses, phases, wheel); write_data(year, ingresses, phases, wheel)
    changed = 0; weeks = date(year, 12, 28).isocalendar().week
    for base in (SOURCE_ROOT, PUBLIC_ROOT):
        for week in range(1, weeks + 1):
            if patch_page(base / str(year) / f"W{week:02d}" / "index.html", ingresses, events): changed += 1
    print(f"{year}: {len(ingresses)} ingresses in query window, {len(wheel)} Wheel-of-the-Year stations in query window, {len(phases)} lunar phases, {changed} pages updated")
    return changed


def parse_years() -> list[int]:
    parser = argparse.ArgumentParser(description="Populate Star Almanack calendar astronomy")
    parser.add_argument("years", metavar="YEAR", type=int, nargs="+", help="ISO years to populate")
    args = parser.parse_args(); years = list(dict.fromkeys(args.years))
    for year in years:
        if not 1900 <= year <= 2100: parser.error(f"YEAR must be between 1900 and 2100: {year}")
    return years


def main() -> None:
    years = parse_years(); total = sum(populate_year(year) for year in years)
    print(f"Updated {total} calendar page files for: {' '.join(map(str, years))}")


if __name__ == "__main__": main()
