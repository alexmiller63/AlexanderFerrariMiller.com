#!/usr/bin/env python3
"""Populate major Star Almanack meteor-shower maxima for requested years.

Each published maximum includes the radiant constellation, expected ZHR,
calculated Moon illumination/interference, and practical observing guidance.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from populate_calendar import horizons_longitudes, interpolate_time, unwrap

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Star-Almanack-Repo" / "site"
PUBLIC_ROOT = ROOT / "almanack"
DATA_ROOT = ROOT / "Star-Almanack-Repo" / "generated"
METEOR_GLYPH = '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/meteor-shower.svg" alt="Meteor shower" aria-label="Meteor shower">'

# Name, nominal solar longitude of maximum, radiant constellation, expected ZHR.
# ZHR values are the Almanack's reader-facing typical expectations, not a promise
# for a particular site or year.
SHOWERS = (
    ("Quadrantids", 283.15, "Boötes", 120),
    ("Lyrids", 32.32, "Lyra", 18),
    ("η-Aquariids", 45.50, "Aquarius", 50),
    ("Southern δ-Aquariids", 128.00, "Aquarius", 25),
    ("α-Capricornids", 128.00, "Capricornus", 5),
    ("Perseids", 140.00, "Perseus", 100),
    ("Orionids", 208.00, "Orion", 20),
    ("Leonids", 235.27, "Leo", 15),
    ("Geminids", 262.20, "Gemini", 150),
    ("Ursids", 270.70, "Ursa Minor", 10),
)
ROW_RE = re.compile(r"<tr><td>((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), [^<]+)</td><td>(.*?)</td><td>(.*?)</td></tr>")
SHOWER_NAMES = tuple(name for name, *_ in SHOWERS)


def crossing(samples, target_deg: float, year: int):
    times = [t for t, _ in samples]; values = unwrap([lon for _, lon in samples])
    k_min = int((values[0] - target_deg) // 360) - 1
    k_max = int((values[-1] - target_deg) // 360) + 1
    for k in range(k_min, k_max + 1):
        target = target_deg + 360.0 * k
        for i in range(len(values) - 1):
            if values[i] <= target <= values[i + 1]:
                ts = interpolate_time(times[i], values[i], times[i + 1], values[i + 1], target)
                if ts.year == year: return ts
                break
    raise RuntimeError(f"No {year} solar-longitude crossing for {target_deg}°")


def longitude_at(samples, ts):
    for i in range(len(samples) - 1):
        t0, lon0 = samples[i]; t1, lon1 = samples[i + 1]
        if t0 <= ts <= t1:
            delta = ((lon1 - lon0 + 180.0) % 360.0) - 180.0
            fraction = 0.0 if t1 == t0 else (ts - t0).total_seconds() / (t1 - t0).total_seconds()
            return (lon0 + delta * fraction) % 360.0
    raise RuntimeError(f"Timestamp {ts.isoformat()} outside ephemeris sample range")


def moon_context(sun_samples, moon_samples, ts):
    sun_lon = longitude_at(sun_samples, ts)
    moon_lon = longitude_at(moon_samples, ts)
    elongation = abs(((moon_lon - sun_lon + 180.0) % 360.0) - 180.0)
    illumination = (1.0 - math.cos(math.radians(elongation))) / 2.0
    percent = int(round(illumination * 100))
    if illumination < 0.20:
        interference = "little moonlight interference"
    elif illumination < 0.50:
        interference = "moderate moonlight interference"
    elif illumination < 0.80:
        interference = "substantial moonlight interference"
    else:
        interference = "strong moonlight interference"
    return percent, interference


def observing_guidance(moon_percent):
    base = "Use a dark site, allow 20–30 minutes for dark adaptation, and observe with the unaided eye."
    if moon_percent >= 50:
        return base + " Put the Moon behind a building, tree, or other obstruction and watch the darkest open sky."
    return base + " Watch a broad area of sky rather than staring directly at the radiant."


def shower_events(year: int):
    start = date(year, 1, 1) - timedelta(days=10)
    stop = date(year + 1, 1, 1) + timedelta(days=10)
    sun = horizons_longitudes("10", start, stop)
    moon = horizons_longitudes("301", start, stop)
    events = []
    for name, lon, constellation, zhr in SHOWERS:
        ts = crossing(sun, lon, year)
        moon_percent, interference = moon_context(sun, moon, ts)
        events.append((name, lon, constellation, zhr, ts, moon_percent, interference))
    return events


def calendar_label(event):
    name, _, constellation, zhr, _, moon_percent, interference = event
    return (
        f"{METEOR_GLYPH} {name} peak · radiant in {constellation} · expected ZHR ≈ {zhr} · "
        f"Moon {moon_percent}% illuminated: {interference} · {observing_guidance(moon_percent)}"
    )


def patch_page(path: Path, additions: dict[date, list[str]]) -> bool:
    if not path.exists(): return False
    text = path.read_text(encoding="utf-8")
    def repl(match: re.Match[str]) -> str:
        label, zodiac, cell = match.groups(); d = datetime.strptime(label, "%a, %b %d, %Y").date()
        existing = [x for x in cell.split("<br>") if x and x != "—"]
        keep = [x for x in existing if not any(name in x and "peak" in x for name in SHOWER_NAMES)]
        merged = additions.get(d, []) + keep
        return f"<tr><td>{label}</td><td>{zodiac}</td><td>{'<br>'.join(merged) if merged else '—'}</td></tr>"
    new = ROW_RE.sub(repl, text)
    if new != text: path.write_text(new, encoding="utf-8"); return True
    return False


def populate_year(year: int) -> int:
    maxima = shower_events(year); additions: dict[date, list[str]] = {}
    for event in maxima:
        ts = event[4]
        additions.setdefault(ts.date(), []).append(calendar_label(event))
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "year": year,
        "basis": "Nominal maximum solar longitude with UTC crossing calculated from JPL Horizons apparent geocentric ecliptic-of-date solar longitude; Moon illumination calculated from Sun-Moon elongation at maximum",
        "showers": [
            {
                "name": name,
                "solar_longitude_deg": lon,
                "radiant_constellation": constellation,
                "expected_zhr": zhr,
                "utc": ts.isoformat().replace("+00:00", "Z"),
                "moon_illumination_percent": moon_percent,
                "moon_interference": interference,
                "observing_guidance": observing_guidance(moon_percent),
                "calendar_label": calendar_label((name, lon, constellation, zhr, ts, moon_percent, interference)),
            }
            for name, lon, constellation, zhr, ts, moon_percent, interference in maxima
        ],
    }
    (DATA_ROOT / f"meteor-showers-{year}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    changed = 0
    for base in (SOURCE_ROOT, PUBLIC_ROOT):
        for path in sorted((base / str(year)).glob("W??/index.html")): changed += int(patch_page(path, additions))
    print(f"{year}: {len(maxima)} shower maxima with radiant/ZHR/Moon/guidance details, {changed} pages updated")
    for name, lon, _, _, ts, moon_percent, interference in maxima:
        print(f"  {name}: λ☉={lon:.2f}° -> {ts.isoformat()} · Moon {moon_percent}% · {interference}")
    return changed


def parse_years() -> list[int]:
    parser = argparse.ArgumentParser(description="Populate Star Almanack meteor showers")
    parser.add_argument("years", metavar="YEAR", type=int, nargs="+", help="Years to populate")
    args = parser.parse_args(); years = list(dict.fromkeys(args.years))
    for year in years:
        if not 1900 <= year <= 2100: parser.error(f"YEAR must be between 1900 and 2100: {year}")
    return years


def main() -> None:
    years = parse_years(); total = sum(populate_year(year) for year in years)
    print(f"Updated {total} meteor-shower page files for: {' '.join(map(str, years))}")


if __name__ == "__main__": main()