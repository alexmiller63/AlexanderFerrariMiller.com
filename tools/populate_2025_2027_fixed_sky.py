#!/usr/bin/env python3
"""Populate 2025 and 2027 fixed-sky visibility events.

Reuses the audited 2026 source catalogs as coordinate/identity inputs and
recomputes best-visibility dates for each requested year under the preserved
Star Almanack rule: alpha_sun = alpha_object - 9h.  The generated calendar
presentation deduplicates observer-facing stellar targets while keeping the
source rows intact in year-specific CSV outputs.
"""
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
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5


def apparent_sun_ra_hours(x: dt.datetime) -> float:
    jd = julian_date(x)
    t = (jd - 2451545.0) / 36525.0
    ml = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360.0
    ma = math.radians((357.52911 + t * (35999.05029 - 0.0001537 * t)) % 360.0)
    c = ((1.914602 - t * (0.004817 + 0.000014 * t)) * math.sin(ma)
         + (0.019993 - 0.000101 * t) * math.sin(2 * ma)
         + 0.000289 * math.sin(3 * ma))
    omega = math.radians(125.04 - 1934.136 * t)
    lam = math.radians((ml + c - 0.00569 - 0.00478 * math.sin(omega)) % 360.0)
    sec = 21.448 - t * (46.8150 + t * (0.00059 - t * 0.001813))
    eps0 = 23.0 + (26.0 + sec / 60.0) / 60.0
    eps = math.radians(eps0 + 0.00256 * math.cos(omega))
    ra = math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))) % 360.0
    return ra / 15.0


def hour_distance(a: float, b: float) -> float:
    return abs((a - b + 12.0) % 24.0 - 12.0)


def best_visibility(ra_h: float, year: int) -> tuple[dt.datetime, dt.date]:
    target = (ra_h - 9.0) % 24.0
    start = dt.datetime(year - 1, 12, 31, 12, 0)
    end = dt.datetime(year, 12, 31, 23, 59)
    best_t, best_d = start, float("inf")
    x = start
    while x <= end:
        d = hour_distance(apparent_sun_ra_hours(x), target)
        if d < best_d:
            best_t, best_d = x, d
        x += dt.timedelta(hours=6)
    lo = max(start, best_t - dt.timedelta(hours=8))
    hi = min(end, best_t + dt.timedelta(hours=8))
    x = lo
    while x <= hi:
        d = hour_distance(apparent_sun_ra_hours(x), target)
        if d < best_d:
            best_t, best_d = x, d
        x += dt.timedelta(minutes=1)
    return best_t, (best_t + dt.timedelta(hours=12)).date()


def iso_label(d: dt.date) -> str:
    y, w, wd = d.isocalendar()
    return f"{y}-W{w:02d}-{wd}"


def read_csv(name: str) -> list[dict[str, str]]:
    with (SRC / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def redated(rows: list[dict[str, str]], year: int) -> list[dict[str, str]]:
    out = []
    for row in rows:
        r = dict(row)
        instant, day = best_visibility(float(r["ra_h"]), year)
        r["best_instant_utc"] = instant.strftime("%Y-%m-%d %H:%M")
        r["best_date"] = day.isoformat()
        r["iso"] = iso_label(day)
        out.append(r)
    return out


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)


def bayer_label(r: dict[str, str]) -> str:
    name = r.get("proper", "").strip()
    bayer = r.get("bayer", "").strip()
    base = f"{name} ({bayer})" if name and bayer else (name or bayer)
    mag = r.get("mag_class", "").strip()
    aid = "👁" if mag and int(mag) <= 3 else "B"
    return f"{base} — {aid} V {mag}" if mag else base


def bright_label(r: dict[str, str]) -> str:
    name = r.get("proper", "").strip()
    if not name:
        b = r.get("bayer", "").strip(); c = r.get("con", "").strip()
        name = f"{b} {c}".strip()
    mag = r.get("mag_class", "").strip()
    return f"{name} — 👁 V {mag}" if mag else name


def page_date_map(year: int) -> dict[dt.date, list[str]]:
    bayer = redated(read_csv("expanded-bayer-visibility-2026.csv"), year)
    bright = redated(read_csv("bright-star-visibility-2026.csv"), year)
    messier = redated(read_csv("messier-visibility-2026.csv"), year)

    write_csv(SRC / "generated" / f"expanded-bayer-visibility-{year}.csv", bayer)
    write_csv(SRC / "generated" / f"bright-star-visibility-{year}.csv", bright)
    write_csv(SRC / "generated" / f"messier-visibility-{year}.csv", messier)

    events: dict[dt.date, list[str]] = defaultdict(list)
    seen: set[tuple[dt.date, str]] = set()

    for r in bayer:
        d = dt.date.fromisoformat(r["best_date"])
        identity = (r.get("proper") or r.get("bayer") or "").strip().lower()
        key = (d, identity)
        if identity and key not in seen:
            events[d].append(bayer_label(r)); seen.add(key)

    for r in bright:
        if r.get("new_non_alpha_beta", "").lower() != "yes":
            continue
        d = dt.date.fromisoformat(r["best_date"])
        identity = (r.get("proper") or (r.get("bayer", "") + r.get("con", ""))).strip().lower()
        key = (d, identity)
        if identity and key not in seen:
            events[d].append(bright_label(r)); seen.add(key)

    for r in messier:
        d = dt.date.fromisoformat(r["best_date"])
        events[d].append(r["messier"] + " — 🔭")

    return events


def inject(root: Path, year: int, events: dict[dt.date, list[str]]) -> int:
    changed = 0
    for page in sorted((root / str(year)).glob("W*/index.html")):
        text = page.read_text(encoding="utf-8")
        original = text
        for d, vals in events.items():
            date_text = d.strftime("%a, %b %d, %Y").replace(" 0", " ")
            pat = re.compile(rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)")
            m = pat.search(text)
            if not m:
                continue
            existing = m.group(2)
            keep = [] if existing == "—" else [x for x in existing.split("<br>") if x]
            for v in vals:
                if v not in keep:
                    keep.append(v)
            text = text[:m.start(2)] + ("<br>".join(keep) if keep else "—") + text[m.end(2):]
        if text != original:
            page.write_text(text, encoding="utf-8"); changed += 1
    return changed


def main() -> None:
    for year in YEARS:
        events = page_date_map(year)
        c1 = inject(SOURCE_SITE, year, events)
        c2 = inject(PUBLIC, year, events)
        print(f"{year}: {sum(len(v) for v in events.values())} fixed-sky events; updated {c1} source + {c2} public pages")


if __name__ == "__main__":
    main()
