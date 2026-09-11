#!/usr/bin/env python3
"""Populate constellation-center events for requested Almanack years.

Alpha/beta star events are owned by the fixed-sky population step;
this step must not create duplicate alpha/beta events.
"""
from __future__ import annotations
import csv
import datetime as dt
import re
import sys
from collections import defaultdict
from pathlib import Path

from star_almanack_astronomy import best_visibility, declination_band, season_for

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
PUBLIC = ROOT / "almanack"
SOURCE_SITE = SRC / "site"
DEFAULT_YEARS = (2025, 2026, 2027)
CENTROID_SNAPSHOT = SRC / "constellation-observance-2026.csv"


def requested_years() -> tuple[int, ...]:
    if len(sys.argv) == 1:
        return DEFAULT_YEARS
    try:
        years = tuple(dict.fromkeys(int(x) for x in sys.argv[1:]))
    except ValueError as exc:
        raise SystemExit("Years must be integers, e.g. 2025 2026 2027") from exc
    if any(y < 1 for y in years):
        raise SystemExit("Years must be positive integers")
    return years


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def iso_label(d):
    y, w, wd = d.isocalendar()
    return f"{y}-W{w:02d}-{wd}"


def build_rows(year):
    snaps = read_csv(CENTROID_SNAPSHOT)
    if len(snaps) != 88:
        raise SystemExit(f"Expected 88 centroid snapshot rows, got {len(snaps)}")
    rows = []
    for snap in snaps:
        ci, cd = best_visibility(float(snap["centroid_ra_h"]), year)
        rows.append({
            "name": snap["name"], "abbr": snap["abbr"],
            "centroid_ra_h": snap["centroid_ra_h"], "centroid_dec_deg": snap["centroid_dec_deg"],
            "sampled_area_sq_deg": snap["sampled_area_sq_deg"], "centroid_step_deg": snap["centroid_step_deg"],
            "center_best_instant_utc": ci.strftime("%Y-%m-%d %H:%M"),
            "center_best_date": cd.isoformat(), "center_iso": iso_label(cd),
        })
    return rows


def write_csv(year, rows):
    out = SRC / "generated" / f"constellation-observance-{year}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def event_map(rows):
    events = defaultdict(list)
    for r in rows:
        d = dt.date.fromisoformat(r["center_best_date"])
        cls = f"{declination_band(r['centroid_dec_deg'])} {season_for(d)}"
        events[d].append(f"✦ {r['name']} center — Constellation — {cls}")
    return events


def clean_legacy_constellation_events(text):
    cells = re.compile(r'(<td>)(.*?)(</td>)')
    bare = re.compile(r'^✦ (?:α|β) star — .+$')
    old_center = re.compile(r'^✦ .*? (?:geometric-center observance|center)(?: —)? .+$')

    def repl(m):
        parts = [p for p in m.group(2).split("<br>") if not bare.match(p.strip()) and not old_center.match(p.strip())]
        return m.group(1) + ("<br>".join(parts) if parts else "—") + m.group(3)

    return cells.sub(repl, text)


def pages_for_events(root, events):
    pages = []
    for iso_year in sorted({d.isocalendar().year for d in events}):
        pages.extend(sorted((root / str(iso_year)).glob("W*/index.html")))
    return pages


def inject(root, events):
    changed = 0
    for page in pages_for_events(root, events):
        text = page.read_text(encoding="utf-8")
        original = text
        text = clean_legacy_constellation_events(text)
        for d, vals in events.items():
            date_text = d.strftime("%a, %b %d, %Y")
            pat = re.compile(rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)")
            m = pat.search(text)
            if not m:
                continue
            keep = [] if m.group(2) == "—" else [x for x in m.group(2).split("<br>") if x]
            for v in vals:
                if v not in keep:
                    keep.append(v)
            text = text[:m.start(2)] + "<br>".join(keep) + text[m.end(2):]
        if text != original:
            page.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def main():
    for year in requested_years():
        rows = build_rows(year)
        write_csv(year, rows)
        events = event_map(rows)
        c1 = inject(SOURCE_SITE, events)
        c2 = inject(PUBLIC, events)
        print(f"{year}: 88 constellation-center events; updated {c1} source + {c2} public pages")


if __name__ == "__main__":
    main()
