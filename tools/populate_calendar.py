#!/usr/bin/env python3
"""Populate Star Almanack calendar astronomy for one or more ISO years.

Year-independent engine using JPL Horizons apparent geocentric ecliptic-of-date
longitudes for the Sun and Moon. Event times are linearly interpolated between
1-hour samples and written to both source and public Almanack trees.

Publication rules enforced here:
- ingress and quarter-day names that describe the same instant are one event;
- equinox/solstice terminology follows the Almanack's traditional naming;
- First Point names are included for Aries and Libra only;
- Full Moons receive the Almanack's astronomical seasonal Moon names;
- no duplicate longitude/time text is emitted for a combined event;
- displayed civil dates and zodiac labels are presentation only; population is
  keyed by machine-readable ISO dates on the calendar rows.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from almanack_calendar import (
    ensure_calendar_metadata,
    get_events,
    page_dates,
    set_events,
    set_zodiac,
)

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
    (0.0, "Vernal equinox", "Ostara"),
    (45.0, "Spring–Summer midpoint", "Beltane"),
    (90.0, "Summer solstice", "Litha"),
    (135.0, "Summer–Autumn midpoint", "Lughnasadh"),
    (180.0, "Autumnal equinox", "Mabon"),
    (225.0, "Autumn–Winter midpoint", "Samhain"),
    (270.0, "Winter solstice", "Yule"),
)
FIRST_POINTS = {0: "First Point of Aries", 180: "First Point of Libra"}
SEASON_NAMES = {
    270: ("Moon After Yule", "Wolf Moon", "Sap Moon"),
    0: ("Seed Moon", "Milk Moon", "Flower Moon"),
    90: ("Hay Moon", "Grain Moon", "Fruit Moon"),
}
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


def _quarter_boundaries(wheel):
    return sorted((ts, int(round(lon)) % 360) for ts, lon, _, _ in wheel if int(round(lon)) % 90 == 0)


def full_moon_names(phases, wheel):
    """Assign the Almanack's seasonal Full-Moon names from calculated astronomy."""
    fulls = sorted(ts for ts, label in phases if label == "🌕 Full Moon")
    quarters = _quarter_boundaries(wheel)
    names: dict[datetime, str] = {}
    for (start, lon), (end, _) in zip(quarters, quarters[1:]):
        in_season = [ts for ts in fulls if start <= ts < end]
        if len(in_season) == 4:
            names[in_season[2]] = "Blue Moon"
    september_equinoxes = [ts for ts, lon in quarters if lon == 180]
    december_solstices = [ts for ts, lon in quarters if lon == 270]
    for eq in september_equinoxes:
        candidates = [ts for ts in fulls if abs((ts - eq).total_seconds()) <= 35 * 86400]
        if candidates:
            names[min(candidates, key=lambda ts: abs((ts - eq).total_seconds()))] = "Harvest Moon"
    for solstice in december_solstices:
        before = [ts for ts in fulls if ts < solstice]
        after = [ts for ts in fulls if ts > solstice]
        if before: names[max(before)] = "Moon Before Yule"
        if after: names[min(after)] = "Moon After Yule"
    for (start, lon), (end, _) in zip(quarters, quarters[1:]):
        if lon not in SEASON_NAMES: continue
        in_season = [ts for ts in fulls if start <= ts < end]
        ordinary = SEASON_NAMES[lon]; ordinary_index = 0
        for ts in in_season:
            if names.get(ts) == "Blue Moon": continue
            if ts in names:
                ordinary_index += 1; continue
            if ordinary_index < len(ordinary): names[ts] = ordinary[ordinary_index]
            ordinary_index += 1
    harvests = sorted(ts for ts, name in names.items() if name == "Harvest Moon")
    before_yules = sorted(ts for ts, name in names.items() if name == "Moon Before Yule")
    for harvest in harvests:
        later = [ts for ts in before_yules if ts > harvest]
        if not later: continue
        end = later[0]; middle = [ts for ts in fulls if harvest < ts < end]
        if middle and (middle[0] not in names or names[middle[0]] != "Blue Moon"):
            names[middle[0]] = "Hunter's Moon"
        for ts in middle[1:]:
            if names.get(ts) != "Blue Moon": names[ts] = "Frost Moon"
    return names


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
    events: dict[date, list[str]] = {}
    moon_names = full_moon_names(phases, wheel)
    wheel_by_longitude = {int(round(lon)) % 360: (ts, astronomical, traditional) for ts, lon, astronomical, traditional in wheel}
    consumed_wheel: set[int] = set()
    for ts, idx in ingresses:
        if not first <= ts.date() <= last: continue
        deg = idx * 30; glyph = f'<span class="zodiac-glyph">{SIGNS[idx]}</span>'
        if deg in (0, 90, 180, 270) and deg in wheel_by_longitude:
            _, astronomical, traditional = wheel_by_longitude[deg]
            names = [f"{glyph} Sun enters {SIGN_NAMES[idx]}", astronomical]
            if deg in FIRST_POINTS: names.append(FIRST_POINTS[deg])
            names.append(traditional); event = " · ".join(names) + f" — {fmt_utc(ts)}"; consumed_wheel.add(deg)
        else:
            event = f"{glyph} Sun enters {SIGN_NAMES[idx]} — {fmt_utc(ts)}"
        events.setdefault(ts.date(), []).append(event)
    for ts, lon, astronomical, traditional in wheel:
        key = int(round(lon)) % 360
        if key in consumed_wheel: continue
        if first <= ts.date() <= last:
            events.setdefault(ts.date(), []).append(f"{traditional} · {astronomical} — {fmt_utc(ts)}")
    for ts, label in phases:
        if not first <= ts.date() <= last: continue
        if label == "🌕 Full Moon" and ts in moon_names: label = f"{label} · {moon_names[ts]}"
        events.setdefault(ts.date(), []).append(f"{label} — {fmt_utc(ts)}")
    return events


def patch_page(path, ingresses, events):
    if not path.exists(): return False
    original = path.read_text(encoding="utf-8")
    text = ensure_calendar_metadata(original, path)
    calendar_prefixes = ("🌑 New Moon", "🌓 First Quarter", "🌕 Full Moon", "🌗 Last Quarter")
    for d in page_dates(path):
        existing_html = get_events(text, d)
        if existing_html is None:
            raise RuntimeError(f"Missing machine-readable calendar row for {d} in {path}")
        existing = [x for x in existing_html.split("<br>") if x and x != "—"]
        generated = events.get(d, [])
        keep = [
            x for x in existing
            if " ingress (" not in x
            and "Sun enters " not in x
            and not x.startswith("Wheel of the Year:")
            and not x.startswith(calendar_prefixes)
            and not any(name in x for _, name, _ in WHEEL_STATIONS)
        ]
        merged = keep + generated
        text, found = set_events(text, d, "<br>".join(merged) if merged else "—")
        if not found: raise RuntimeError(f"Could not update Events for {d} in {path}")
        idx, n = zodiac_for_day(d, ingresses)
        rendered = f'<span class="zodiac-glyph">{SIGNS[idx]}</span> {n}'
        text, found = set_zodiac(text, d, sign_name=SIGN_NAMES[idx], zodiac_day=n, rendered_html=rendered)
        if not found: raise RuntimeError(f"Could not update Zodiac day for {d} in {path}")
    if text != original:
        path.write_text(text, encoding="utf-8"); return True
    return False


def write_data(year, ingresses, phases, wheel):
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    names = full_moon_names(phases, wheel)
    payload = {
        "year": year,
        "basis": "JPL Horizons apparent geocentric ecliptic-of-date longitude; 1-hour sampling with linear interpolation",
        "solar_ingresses": [{"utc": ts.isoformat().replace("+00:00", "Z"), "sign": SIGNS[idx], "name": SIGN_NAMES[idx], "longitude_deg": idx * 30} for ts, idx in ingresses],
        "wheel_of_the_year": [{"utc": ts.isoformat().replace("+00:00", "Z"), "longitude_deg": int(lon), "astronomical_name": astronomical, "traditional_name": traditional} for ts, lon, astronomical, traditional in wheel],
        "lunar_phases": [{"utc": ts.isoformat().replace("+00:00", "Z"), "phase": label, **({"moon_name": names[ts]} if label == "🌕 Full Moon" and ts in names else {})} for ts, label in phases],
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
    print(f"{year}: {len(ingresses)} ingresses in query window, {len(wheel)} solar stations in query window, {len(phases)} lunar phases, {changed} pages updated")
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
