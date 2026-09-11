#!/usr/bin/env python3
"""Render Messier calendar events in the Star Almanack canonical form.

M# [, common name], editorial type in constellation, instrument V magnitude, Declination Band Season.
Astronomical identity, magnitude and declination come from fixed-objects.yaml;
observing aid is derived from magnitude through the shared Almanack rule.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import catalog_common_names as names
import populate_fixed_sky as fixed
from star_almanack_objects import observing_aid_for_magnitude, HTML_AID

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
PUBLIC = ROOT / "almanack"
SOURCE_SITE = SRC / "site"
FIXED = SRC / "fixed-objects.yaml"
EDITORIAL = json.loads((SRC / "messier-editorial.json").read_text(encoding="utf-8"))
DEFAULT_YEARS = (2025, 2026, 2027)


def requested_years() -> tuple[int, ...]:
    if len(sys.argv) == 1:
        return DEFAULT_YEARS
    try:
        years = tuple(dict.fromkeys(int(value) for value in sys.argv[1:]))
    except ValueError as exc:
        raise SystemExit("Years must be integers, e.g. 2025 2026 2027") from exc
    if any(year < 1 for year in years):
        raise SystemExit("Years must be positive integers")
    return years


def load_catalog() -> dict[str, dict[str, str]]:
    out = {}
    active = False
    for raw in FIXED.read_text(encoding="utf-8").splitlines():
        if raw == "messier:":
            active = True
            continue
        if active and raw and not raw.startswith(" "):
            break
        if not active:
            continue
        m = re.match(r"\s*-\s*\[(.*)\]\s*$", raw)
        if not m:
            continue
        row = next(csv.reader([m.group(1)], skipinitialspace=True))
        if len(row) < 9 or not re.fullmatch(r"M\d{1,3}", row[0].strip()):
            continue
        designation = row[0].strip().upper()
        name = row[2].strip()
        if name.casefold() == "null":
            name = ""
        edit = EDITORIAL["objects"].get(designation, {})
        name = edit.get("accepted_name", name) or ""
        name = names.preferred_messier_name(designation, name)
        typ = edit.get("editorial_type", EDITORIAL["type_labels"].get(row[3].strip(), row[3].strip()))
        con = EDITORIAL["constellation_labels"].get(row[4].strip(), row[4].strip())
        out[designation] = {
            "id": designation, "name": name, "type": typ, "con": con,
            "ra_h": row[5].strip(), "dec_deg": row[6].strip(), "mag": row[7].strip(),
        }
    if len(out) != 110:
        raise RuntimeError(f"Expected 110 Messier objects, found {len(out)}")
    return out


def label(r: dict[str, str], day: dt.date) -> str:
    head = r["id"]
    if r["name"]:
        head += f', {r["name"]}'
    head += f', {r["type"]} in {r["con"]}'
    aid = observing_aid_for_magnitude(r["mag"])
    glyph = HTML_AID[aid] if aid is not None else ""
    mag = r["mag"]
    vis = " ".join(part for part in (glyph, f"V {mag}" if mag else "") if part)
    vis_html = f'<span class="visibility-magnitude">{vis}</span>' if vis else ""
    parts = [head]
    if vis_html:
        parts.append(vis_html)
    parts.append(f"{fixed.declination_band(r['dec_deg'])} {fixed.season_for(day)}")
    return " — ".join(parts)


def events(catalog, year):
    out = defaultdict(list)
    visibility = {row["messier"]: row for row in fixed.redated_preserving_2026_phase(fixed.read_csv("messier-visibility-2026.csv"), year)}
    for designation in sorted(catalog, key=lambda x: int(x[1:])):
        r = catalog[designation]
        day = dt.date.fromisoformat(visibility[designation]["best_date"])
        out[day].append(label(r, day))
    return out


def is_messier_event(item: str) -> bool:
    plain = re.sub(r"<[^>]+>", "", item).strip()
    return bool(re.match(r"^(?:Messier\s+\d+\s+\(M\d+\)|M\d+\b|[^—]+\s+\(M\d+\),)", plain))


def pages_for_events(root: Path, by_date) -> list[Path]:
    pages = []
    for iso_year in sorted({day.isocalendar().year for day in by_date}):
        pages.extend(sorted((root / str(iso_year)).glob("W??/index.html")))
    return pages


def inject(root: Path, by_date) -> int:
    changed = 0
    for page in pages_for_events(root, by_date):
        text = page.read_text(encoding="utf-8")
        original = text
        for day, labels in by_date.items():
            date_text = day.strftime("%a, %b %d, %Y").replace(" 0", " ")
            pat = re.compile(rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)")
            m = pat.search(text)
            if not m:
                continue
            keep = [] if m.group(2) == "—" else [x for x in m.group(2).split("<br>") if x and not is_messier_event(x)]
            keep.extend(labels)
            replacement = "<br>".join(keep) if keep else "—"
            text = text[:m.start(2)] + replacement + text[m.end(2):]
        if text != original:
            page.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def main():
    catalog = load_catalog()
    for year in requested_years():
        e = events(catalog, year)
        a = inject(SOURCE_SITE, e)
        b = inject(PUBLIC, e)
        print(f"{year}: standardized 110 Messier events; updated {a} source + {b} public pages")

if __name__ == "__main__":
    main()
