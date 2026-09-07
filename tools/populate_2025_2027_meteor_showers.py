#!/usr/bin/env python3
"""Populate major meteor-shower maxima for the 2025 and 2027 Almanacks.

The shared shower definitions use the solar longitude of the nominal maximum.
That makes civil dates year-dependent instead of copying a fixed date from 2026.
The solar longitude is evaluated with the same JPL Horizons Sun ephemeris used by
the calendar engine. Annual IMO calendars remain the independent verification
layer for special stream-model predictions and observing circumstances.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

from populate_2025_2027_calendar import horizons_longitudes, interpolate_time, unwrap

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Star-Almanack-Repo" / "site"
PUBLIC_ROOT = ROOT / "almanack"
DATA_ROOT = ROOT / "Star-Almanack-Repo" / "generated"
YEARS = (2025, 2027)

# Major showers already promoted in the 2026 reference Almanack.
# λ☉ values are nominal maximum solar longitudes from the IMO working list.
SHOWERS = (
    ("Quadrantids", 283.15, "☄ Quadrantids peak"),
    ("Lyrids", 32.32, "☄ Lyrids peak"),
    ("η-Aquariids", 45.50, "☄ η-Aquariids peak"),
    ("Southern δ-Aquariids", 128.00, "☄ Southern δ-Aquariids peak"),
    ("α-Capricornids", 128.00, "☄ α-Capricornids peak"),
    ("Perseids", 140.00, "☄ Perseids peak"),
    ("Orionids", 208.00, "☄ Orionids peak"),
    ("Leonids", 235.27, "☄ Leonids peak"),
    ("Geminids", 262.20, "☄ Geminids peak"),
    ("Ursids", 270.70, "☄ Ursids peak"),
)

ROW_RE = re.compile(
    r"<tr><td>((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), [^<]+)</td><td>(.*?)</td><td>(.*?)</td></tr>"
)
KNOWN_LABELS = tuple(label for _, _, label in SHOWERS)


def crossing(samples, target_deg: float):
    times = [t for t, _ in samples]
    values = unwrap([lon for _, lon in samples])
    target = target_deg
    while target < values[0]:
        target += 360.0
    for i in range(len(values) - 1):
        if values[i] <= target <= values[i + 1]:
            return interpolate_time(times[i], values[i], times[i + 1], values[i + 1], target)
    raise RuntimeError(f"No solar-longitude crossing for {target_deg}°")


def shower_events(year: int):
    samples = horizons_longitudes("10", date(year, 1, 1) - timedelta(days=10), date(year + 1, 1, 1) + timedelta(days=10))
    out = []
    for name, lon, label in SHOWERS:
        ts = crossing(samples, lon)
        if ts.year != year:
            raise RuntimeError(f"{year} {name}: computed maximum outside civil year: {ts.isoformat()}")
        out.append((name, lon, label, ts))
    return out


def patch_page(path: Path, additions: dict[date, list[str]]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")

    def repl(match: re.Match[str]) -> str:
        label, zodiac, cell = match.groups()
        d = date.fromisoformat(__import__("datetime").datetime.strptime(label, "%a, %b %d, %Y").date().isoformat())
        existing = [x for x in cell.split("<br>") if x and x != "—"]
        keep = [x for x in existing if x not in KNOWN_LABELS]
        merged = additions.get(d, []) + keep
        return f"<tr><td>{label}</td><td>{zodiac}</td><td>{'<br>'.join(merged) if merged else '—'}</td></tr>"

    new = ROW_RE.sub(repl, text)
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def populate_year(year: int) -> int:
    maxima = shower_events(year)
    additions: dict[date, list[str]] = {}
    for _, _, label, ts in maxima:
        additions.setdefault(ts.date(), []).append(label)

    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "year": year,
        "basis": "Nominal maximum solar longitude from the IMO working list; UTC crossing calculated from JPL Horizons apparent geocentric ecliptic-of-date solar longitude",
        "showers": [
            {
                "name": name,
                "solar_longitude_deg": lon,
                "utc": ts.isoformat().replace("+00:00", "Z"),
                "calendar_label": label,
            }
            for name, lon, label, ts in maxima
        ],
    }
    (DATA_ROOT / f"meteor-showers-{year}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    changed = 0
    for base in (SOURCE_ROOT, PUBLIC_ROOT):
        for path in sorted((base / str(year)).glob("W??/index.html")):
            changed += int(patch_page(path, additions))

    print(f"{year}: {len(maxima)} shower maxima, {changed} pages updated")
    for name, lon, _, ts in maxima:
        print(f"  {name}: λ☉={lon:.2f}° -> {ts.isoformat()}")
    return changed


def main() -> None:
    total = sum(populate_year(year) for year in YEARS)
    print(f"Updated {total} meteor-shower page files")


if __name__ == "__main__":
    main()
