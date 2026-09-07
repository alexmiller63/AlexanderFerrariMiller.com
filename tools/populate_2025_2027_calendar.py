#!/usr/bin/env python3
"""Populate 2025 and 2027 Zodiac Days, solar ingresses, and lunar phases.

The calculation is year-independent and uses JPL Horizons apparent geocentric
Ecliptic-of-date longitudes for the Sun and Moon.  Event times are obtained by
linear interpolation between 1-hour samples.  The resulting data are written
back into both the durable placeholder source tree and the public Almanack tree.
"""
from __future__ import annotations

import csv
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Star-Almanack-Repo" / "site"
PUBLIC_ROOT = ROOT / "almanack"
DATA_ROOT = ROOT / "Star-Almanack-Repo" / "generated"
YEARS = (2025, 2027)
SIGNS = "♈♉♊♋♌♍♎♏♐♑♒♓"
SIGN_NAMES = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)
PHASES = ((0.0, "🌑 New Moon"), (90.0, "🌓 First Quarter"),
          (180.0, "🌕 Full Moon"), (270.0, "🌗 Last Quarter"))
HORIZONS_API = "https://ssd.jpl.nasa.gov/api/horizons.api"


def iso_bounds(year: int) -> tuple[date, date]:
    first = date.fromisocalendar(year, 1, 1)
    weeks = date(year, 12, 28).isocalendar().week
    last = date.fromisocalendar(year, weeks, 7)
    return first, last


def jd_to_datetime(jd: float) -> datetime:
    # Unix epoch 1970-01-01 00:00 UTC = JD 2440587.5.
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(days=jd - 2440587.5)


def horizons_longitudes(command: str, start: date, stop: date) -> list[tuple[datetime, float]]:
    params = {
        "format": "json",
        "COMMAND": f"'{command}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",
        "START_TIME": f"'{start.isoformat()} 00:00'",
        "STOP_TIME": f"'{stop.isoformat()} 00:00'",
        "STEP_SIZE": "'1 h'",
        "QUANTITIES": "'31'",
        "CSV_FORMAT": "'YES'",
        "ANG_FORMAT": "'DEG'",
        "CAL_FORMAT": "'JD'",
        "TIME_DIGITS": "'SECONDS'",
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
    start_i = lines.index("$$SOE") + 1
    stop_i = lines.index("$$EOE")
    out: list[tuple[datetime, float]] = []
    for line in lines[start_i:stop_i]:
        if not line.strip():
            continue
        row = next(csv.reader([line]))
        jd = float(row[0].strip())
        out.append((jd_to_datetime(jd), float(row[lon_index].strip()) % 360.0))
    return out


def unwrap(values: list[float]) -> list[float]:
    if not values:
        return []
    out = [values[0]]
    for raw in values[1:]:
        prev = out[-1]
        candidate = raw
        while candidate - prev > 180.0:
            candidate -= 360.0
        while candidate - prev < -180.0:
            candidate += 360.0
        out.append(candidate)
    return out


def interpolate_time(t0: datetime, v0: float, t1: datetime, v1: float, target: float) -> datetime:
    if v1 == v0:
        return t0
    f = (target - v0) / (v1 - v0)
    f = min(1.0, max(0.0, f))
    return t0 + (t1 - t0) * f


def solar_ingresses(samples: list[tuple[datetime, float]]) -> list[tuple[datetime, int]]:
    times = [t for t, _ in samples]
    u = unwrap([x for _, x in samples])
    events: list[tuple[datetime, int]] = []
    lo = int(u[0] // 30) - 1
    hi = int(u[-1] // 30) + 1
    targets = [30.0 * k for k in range(lo, hi + 1)]
    j = 0
    for target in targets:
        while j + 1 < len(u) and u[j + 1] < target:
            j += 1
        if j + 1 >= len(u):
            break
        if u[j] <= target <= u[j + 1]:
            ts = interpolate_time(times[j], u[j], times[j + 1], u[j + 1], target)
            sign_index = int(round(target / 30.0)) % 12
            events.append((ts, sign_index))
    return events


def lunar_phases(sun: list[tuple[datetime, float]], moon: list[tuple[datetime, float]]) -> list[tuple[datetime, str]]:
    if len(sun) != len(moon):
        raise RuntimeError("Sun and Moon sample counts differ")
    times = [t for t, _ in sun]
    elong = unwrap([((m - s) % 360.0) for (_, s), (_, m) in zip(sun, moon)])
    events: list[tuple[datetime, str]] = []
    lo = int(elong[0] // 90) - 1
    hi = int(elong[-1] // 90) + 1
    j = 0
    for k in range(lo, hi + 1):
        target = 90.0 * k
        while j + 1 < len(elong) and elong[j + 1] < target:
            j += 1
        if j + 1 >= len(elong):
            break
        if elong[j] <= target <= elong[j + 1]:
            ts = interpolate_time(times[j], elong[j], times[j + 1], elong[j + 1], target)
            label = PHASES[k % 4][1]
            events.append((ts, label))
    return events


def zodiac_for_day(d: date, ingresses: list[tuple[datetime, int]]) -> tuple[int, int]:
    eligible = [(ts.date(), idx) for ts, idx in ingresses if ts.date() <= d]
    if not eligible:
        raise RuntimeError(f"No preceding ingress available for {d}")
    ingress_day, idx = eligible[-1]
    return idx, (d - ingress_day).days + 1


def zodiac_label(d: date, ingresses: list[tuple[datetime, int]]) -> str:
    idx, n = zodiac_for_day(d, ingresses)
    if n == 1:
        return f"{SIGNS[idx]} ({SIGN_NAMES[idx]}) 1"
    return f"{SIGNS[idx]} {n}"


def fmt_utc(ts: datetime) -> str:
    ts = ts.astimezone(timezone.utc)
    return ts.strftime("%H:%M:%S UTC")


def build_events(first: date, last: date, ingresses: list[tuple[datetime, int]], phases: list[tuple[datetime, str]]) -> dict[date, list[str]]:
    events: dict[date, list[str]] = {}
    for ts, idx in ingresses:
        if first <= ts.date() <= last:
            deg = idx * 30
            events.setdefault(ts.date(), []).append(
                f"{SIGNS[idx]} {SIGN_NAMES[idx]} ingress ({deg}°) — {fmt_utc(ts)}"
            )
    for ts, label in phases:
        if first <= ts.date() <= last:
            events.setdefault(ts.date(), []).append(f"{label} — {fmt_utc(ts)}")
    return events


ROW_RE = re.compile(
    r"<tr><td>((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), [^<]+)</td><td>.*?</td><td>(.*?)</td></tr>"
)


def parse_page_date(label: str) -> date:
    return datetime.strptime(label, "%a, %b %d, %Y").date()


def patch_page(path: Path, ingresses: list[tuple[datetime, int]], events: dict[date, list[str]]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")

    def repl(match: re.Match[str]) -> str:
        label = match.group(1)
        d = parse_page_date(label)
        z = zodiac_label(d, ingresses)
        existing = [x for x in match.group(2).split("<br>") if x and x != "—"]
        generated = events.get(d, [])
        # Replace prior generated ingress/phase rows while preserving other calendar events.
        keep = [x for x in existing if " ingress (" not in x and not x.startswith(("🌑 New Moon", "🌓 First Quarter", "🌕 Full Moon", "🌗 Last Quarter"))]
        merged = keep + generated
        event_html = "<br>".join(merged) if merged else "—"
        return f"<tr><td>{label}</td><td>{z}</td><td>{event_html}</td></tr>"

    new = ROW_RE.sub(repl, text)
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def write_data(year: int, ingresses: list[tuple[datetime, int]], phases: list[tuple[datetime, str]]) -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "year": year,
        "basis": "JPL Horizons apparent geocentric ecliptic-of-date longitude; 1-hour sampling with linear interpolation",
        "solar_ingresses": [
            {"utc": ts.isoformat().replace("+00:00", "Z"), "sign": SIGNS[idx], "name": SIGN_NAMES[idx], "longitude_deg": idx * 30}
            for ts, idx in ingresses
        ],
        "lunar_phases": [
            {"utc": ts.isoformat().replace("+00:00", "Z"), "phase": label}
            for ts, label in phases
        ],
    }
    (DATA_ROOT / f"calendar-{year}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def populate_year(year: int) -> int:
    first, last = iso_bounds(year)
    query_start = first - timedelta(days=45)
    query_stop = last + timedelta(days=45)
    sun = horizons_longitudes("10", query_start, query_stop)
    moon = horizons_longitudes("301", query_start, query_stop)
    ingresses = solar_ingresses(sun)
    phases = lunar_phases(sun, moon)
    events = build_events(first, last, ingresses, phases)
    write_data(year, ingresses, phases)

    changed = 0
    weeks = date(year, 12, 28).isocalendar().week
    for base in (SOURCE_ROOT, PUBLIC_ROOT):
        for week in range(1, weeks + 1):
            if patch_page(base / str(year) / f"W{week:02d}" / "index.html", ingresses, events):
                changed += 1
    print(f"{year}: {len(ingresses)} ingresses in query window, {len(phases)} lunar phases, {changed} pages updated")
    return changed


def main() -> None:
    total = sum(populate_year(year) for year in YEARS)
    print(f"Updated {total} calendar page files")


if __name__ == "__main__":
    main()
