#!/usr/bin/env python3
"""Audit the interactive ephemeris observing clock minute-by-minute.

Reads a generated weekly Almanack page and reproduces the browser's altitude
and sky-state rules.  The report makes it easy to see whether each solar-system
body ever has an above-horizon interval in daylight, each twilight band, or
night, without manually circling the clock.

Usage:
    python tools/audit_ephemeris_observing_clock.py 2026 1
    python tools/audit_ephemeris_observing_clock.py 2026 1 --latitude 45
"""
from __future__ import annotations

import argparse
import html
import math
import re
from pathlib import Path

SUN_HORIZON_DEG = -0.8333
TARGET_HORIZON_DEG = -0.5667

def altitude(dec_deg: float, latitude: float, hour_angle_deg: float) -> float:
    dec = math.radians(dec_deg)
    phi = math.radians(latitude)
    ha = math.radians(hour_angle_deg)
    return math.degrees(math.asin(
        math.sin(phi) * math.sin(dec)
        + math.cos(phi) * math.cos(dec) * math.cos(ha)
    ))

def sky_state(sun_alt: float) -> str:
    if sun_alt >= SUN_HORIZON_DEG:
        return "Daylight"
    if sun_alt >= -6:
        return "Civil twilight"
    if sun_alt >= -12:
        return "Nautical twilight"
    if sun_alt >= -18:
        return "Astronomical twilight"
    return "Night"

def attrs(tag: str) -> dict[str, str]:
    return {
        key: html.unescape(value)
        for key, value in re.findall(r'(data-[\w-]+)="([^"]*)"', tag)
    }

def hhmm(minute: int) -> str:
    minute %= 1440
    return f"{minute // 60:02d}:{minute % 60:02d}"

def compress(values: list[str]) -> list[tuple[int, int, str]]:
    if not values:
        return []
    out = []
    start = 0
    current = values[0]
    for i in range(1, len(values)):
        if values[i] != current:
            out.append((start, i, current))
            start, current = i, values[i]
    out.append((start, len(values), current))
    return out

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("year", type=int)
    ap.add_argument("week", type=int)
    ap.add_argument("--latitude", type=float, default=45.0)
    args = ap.parse_args()

    path = Path(f"almanack/{args.year}/W{args.week:02d}/index.html")
    text = path.read_text(encoding="utf-8")

    # Body labels occur in the same column order as observing cells: first the
    # seven primary bodies, then the four extended bodies.
    body_names = re.findall(r'data-latin="(Sun|Moon|Mercury|Venus|Mars|Jupiter|Saturn|Ceres|Uranus|Neptune|Pluto)"', text)
    seen = []
    for name in body_names:
        if name not in seen:
            seen.append(name)
    body_names = seen[:11]

    tags = re.findall(r'<td class="ephemeris-observing"[^>]*>', text)
    if len(tags) < len(body_names):
        raise SystemExit(f"Expected observing cells for {len(body_names)} bodies; found {len(tags)}")

    print(f"{args.year}-W{args.week:02d} observing-clock audit at latitude {args.latitude:+g} degrees")
    print("Minute-by-minute Local Apparent Time; below-horizon takes priority.\n")

    for name, tag in zip(body_names, tags):
        a = attrs(tag)
        ra = float(a["data-ra-hours"])
        dec = float(a["data-dec-deg"])
        sun_ra = float(a["data-sun-ra-hours"])
        sun_dec = float(a["data-sun-dec-deg"])
        is_sun = a.get("data-sun-special") == "true"
        states = []
        for minute in range(1440):
            local_hour = minute / 60.0
            solar_ha = (local_hour - 12.0) * 15.0
            sun_alt = altitude(sun_dec, args.latitude, solar_ha)
            state = sky_state(sun_alt)
            if is_sun:
                states.append(state)
                continue
            target_ha = solar_ha + (sun_ra - ra) * 15.0
            target_alt = altitude(dec, args.latitude, target_ha)
            states.append("Below horizon" if target_alt < TARGET_HORIZON_DEG else state)

        intervals = compress(states)
        above = [(s, e, state) for s, e, state in intervals if state != "Below horizon"]
        rendered = "; ".join(f"{hhmm(s)}-{hhmm(e)} {state}" for s, e, state in above)
        print(f"{name:8s}: {rendered or 'never above horizon'}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
