#!/usr/bin/env python3
"""Populate 2025 and 2027 fixed-sky visibility events."""
from __future__ import annotations
import csv
import datetime as dt
import math
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
PUBLIC = ROOT / "almanack"
SOURCE_SITE = SRC / "site"
YEARS = (2025, 2027)


def julian_date(x: dt.datetime) -> float:
    year, month = x.year, x.month
    day = x.day + (x.hour + (x.minute + x.second / 60.0) / 60.0) / 24.0
    if month <= 2: year -= 1; month += 12
    a = year // 100; b = 2 - a + a // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5


def apparent_sun_ra_hours(x: dt.datetime) -> float:
    jd = julian_date(x); t = (jd - 2451545.0) / 36525.0
    ml = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360.0
    ma = math.radians((357.52911 + t * (35999.05029 - 0.0001537 * t)) % 360.0)
    c = ((1.914602 - t * (0.004817 + 0.000014 * t)) * math.sin(ma) + (0.019993 - 0.000101 * t) * math.sin(2 * ma) + 0.000289 * math.sin(3 * ma))
    omega = math.radians(125.04 - 1934.136 * t)
    lam = math.radians((ml + c - 0.00569 - 0.00478 * math.sin(omega)) % 360.0)
    sec = 21.448 - t * (46.8150 + t * (0.00059 - t * 0.001813))
    eps0 = 23.0 + (26.0 + sec / 60.0) / 60.0
    eps = math.radians(eps0 + 0.00256 * math.cos(omega))
    return (math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))) % 360.0) / 15.0


def hour_distance(a: float, b: float) -> float: return abs((a - b + 12.0) % 24.0 - 12.0)


def best_visibility(ra_h: float, year: int) -> tuple[dt.datetime, dt.date]:
    target = (ra_h - 9.0) % 24.0; start = dt.datetime(year - 1, 12, 31, 12); end = dt.datetime(year, 12, 31, 23, 59)
    best_t, best_d = start, float("inf"); x = start
    while x <= end:
        d = hour_distance(apparent_sun_ra_hours(x), target)
        if d < best_d: best_t, best_d = x, d
        x += dt.timedelta(hours=6)
    x = max(start, best_t - dt.timedelta(hours=8)); hi = min(end, best_t + dt.timedelta(hours=8))
    while x <= hi:
        d = hour_distance(apparent_sun_ra_hours(x), target)
        if d < best_d: best_t, best_d = x, d
        x += dt.timedelta(minutes=1)
    return best_t, (best_t + dt.timedelta(hours=12)).date()


def iso_label(d: dt.date) -> str:
    y, w, wd = d.isocalendar(); return f"{y}-W{w:02d}-{wd}"


def read_csv(name: str) -> list[dict[str, str]]:
    with (SRC / name).open(newline="", encoding="utf-8") as f: return list(csv.DictReader(f))


def redated(rows, year):
    out = []
    for row in rows:
        r = dict(row); instant, day = best_visibility(float(r["ra_h"]), year)
        r["best_instant_utc"] = instant.strftime("%Y-%m-%d %H:%M"); r["best_date"] = day.isoformat(); r["iso"] = iso_label(day); out.append(r)
    return out


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def declination_band(dec: str) -> str:
    value = float(dec)
    return "Northern" if value > 23.44 else "Southern" if value < -23.44 else "Tropical"


def season_for(d: dt.date) -> str:
    md = (d.month, d.day)
    if (3, 20) <= md < (6, 21): return "Spring"
    if (6, 21) <= md < (9, 22): return "Summer"
    if (9, 22) <= md < (12, 21): return "Autumn"
    return "Winter"


def star_label(r: dict[str, str]) -> str:
    proper = r.get("proper", "").strip(); bayer = r.get("bayer", "").strip()
    base = f"{proper} ({bayer})" if proper and bayer else (proper or bayer or f"{r.get('con','').strip()} star")
    mag = r.get("mag_class", "").strip()
    aid = "👁" if mag and int(mag) <= 3 else "B"
    parts = [base]
    if mag: parts.append(f"{aid} V {mag}")
    parts.append(f"{declination_band(r['dec_deg'])} {season_for(dt.date.fromisoformat(r['best_date']))}")
    return " — ".join(parts)


def page_date_map(year: int):
    bayer = redated(read_csv("expanded-bayer-visibility-2026.csv"), year)
    bright = redated(read_csv("bright-star-visibility-2026.csv"), year)
    messier = redated(read_csv("messier-visibility-2026.csv"), year)
    write_csv(SRC / "generated" / f"expanded-bayer-visibility-{year}.csv", bayer)
    write_csv(SRC / "generated" / f"bright-star-visibility-{year}.csv", bright)
    write_csv(SRC / "generated" / f"messier-visibility-{year}.csv", messier)
    events = defaultdict(list); seen = set()
    for r in bayer:
        d = dt.date.fromisoformat(r["best_date"]); identity = (r.get("proper") or r.get("bayer") or "").strip().lower(); key = (d, identity)
        if identity and key not in seen: events[d].append(star_label(r)); seen.add(key)
    for r in bright:
        if r.get("new_non_alpha_beta", "").lower() != "yes": continue
        d = dt.date.fromisoformat(r["best_date"]); identity = (r.get("proper") or (r.get("bayer", "") + r.get("con", ""))).strip().lower(); key = (d, identity)
        if identity and key not in seen: events[d].append(star_label(r)); seen.add(key)
    for r in messier: events[dt.date.fromisoformat(r["best_date"])].append(r["messier"] + " — 🔭")
    return events


def inject(root: Path, year: int, events) -> int:
    changed = 0
    for page in sorted((root / str(year)).glob("W*/index.html")):
        text = page.read_text(encoding="utf-8"); original = text
        for d, vals in events.items():
            date_text = d.strftime("%a, %b %d, %Y").replace(" 0", " ")
            pat = re.compile(rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)"); m = pat.search(text)
            if not m: continue
            keep = [] if m.group(2) == "—" else [x for x in m.group(2).split("<br>") if x]
            for v in vals:
                base = v.split(" — ", 1)[0]
                keep = [x for x in keep if not (x == base or x.startswith(base + " — "))]
                keep.append(v)
            text = text[:m.start(2)] + ("<br>".join(keep) if keep else "—") + text[m.end(2):]
        if text != original: page.write_text(text, encoding="utf-8"); changed += 1
    return changed


def main():
    for year in YEARS:
        events = page_date_map(year); c1 = inject(SOURCE_SITE, year, events); c2 = inject(PUBLIC, year, events)
        print(f"{year}: canonical fixed-sky entries with declination band and season; updated {c1} source + {c2} public pages")

if __name__ == "__main__": main()
