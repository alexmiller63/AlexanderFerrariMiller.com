#!/usr/bin/env python3
"""Render Messier calendar events in the Star Almanack canonical form.

M# [, common name], editorial type in constellation — instrument V magnitude — Declination Band Season

The 2026 calendar is the source of truth for the established observing-aid choice.
Astronomical identity, magnitude and declination come from fixed-objects.yaml.
"""
from __future__ import annotations

import csv
import datetime as dt
import importlib.util
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
PUBLIC = ROOT / "almanack"
SOURCE_SITE = SRC / "site"
FIXED = SRC / "fixed-objects.yaml"
EDITORIAL = json.loads((SRC / "messier-editorial.json").read_text(encoding="utf-8"))
YEARS = (2025, 2026, 2027)

spec = importlib.util.spec_from_file_location("fixedsky", ROOT / "tools" / "populate_2025_2027_fixed_sky.py")
fixed = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(fixed)

GLYPHS = {
    "👁": '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/eye.svg" alt="Naked eye" aria-label="Naked eye" style="height:1.15em;width:auto;vertical-align:-.18em">',
    "B": '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/binoculars.svg" alt="Binoculars" aria-label="Binoculars" style="height:1.15em;width:auto;vertical-align:-.18em">',
    "🔭": '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/telescope.svg" alt="Telescope" aria-label="Telescope" style="height:1.15em;width:auto;vertical-align:-.18em">',
}


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
        typ = edit.get("editorial_type", EDITORIAL["type_labels"].get(row[3].strip(), row[3].strip()))
        con = EDITORIAL["constellation_labels"].get(row[4].strip(), row[4].strip())
        out[designation] = {
            "id": designation, "name": name, "type": typ, "con": con,
            "ra_h": row[5].strip(), "dec_deg": row[6].strip(), "mag": row[7].strip(),
        }
    if len(out) != 110:
        raise RuntimeError(f"Expected 110 Messier objects, found {len(out)}")
    return out


def instrument_map() -> dict[str, str]:
    """Preserve the established 2026 editorial observing-aid choices.

    The 2026 pages contain both legacy text glyphs and the newer rendered SVG
    visibility glyphs.  Read either representation so a presentation-layer
    change cannot make the observing-aid source of truth disappear.
    """
    aids = {}
    designation_patterns = (
        re.compile(r"\b(M\d{1,3})\b"),
        re.compile(r"\bMessier\s+\d+\s+\((M\d{1,3})\)"),
    )
    rendered_aids = {
        'alt="Naked eye"': "👁",
        'alt="Binoculars"': "B",
        'alt="Telescope"': "🔭",
    }

    for root in (PUBLIC, SOURCE_SITE):
        for page in sorted((root / "2026").glob("W??/index.html")):
            text = page.read_text(encoding="utf-8")
            for item in text.split("<br>"):
                designation = None
                for pat in designation_patterns:
                    m = pat.search(item)
                    if m:
                        designation = m.group(1).upper()
                        break
                if not designation:
                    continue

                aid = None
                for marker, value in rendered_aids.items():
                    if marker in item:
                        aid = value
                        break
                if aid is None:
                    plain = re.sub(r"<[^>]+>", "", item)
                    m = re.search(r" — (👁|B|🔭)(?:\s+V\s+[0-9.]+)? —", plain)
                    if m:
                        aid = m.group(1)

                if aid:
                    aids.setdefault(designation, aid)
    return aids


def label(r: dict[str, str], aid: str, day: dt.date) -> str:
    head = r["id"]
    if r["name"]:
        head += f', {r["name"]}'
    head += f', {r["type"]} in {r["con"]}'
    glyph = GLYPHS[aid]
    mag = r["mag"]
    vis = f'{glyph} V {mag}' if mag else glyph
    return f'{head} — <span class="visibility-magnitude">{vis}</span> — {fixed.declination_band(r["dec_deg"])} {fixed.season_for(day)}'


def events(catalog, aids, year):
    out = defaultdict(list)
    for designation in sorted(catalog, key=lambda x: int(x[1:])):
        r = catalog[designation]
        _, day = fixed.best_visibility(float(r["ra_h"]), year)
        out[day].append(label(r, aids.get(designation, "🔭"), day))
    return out


def is_messier_event(item: str) -> bool:
    plain = re.sub(r"<[^>]+>", "", item).strip()
    return bool(re.match(r"^(?:Messier\s+\d+\s+\(M\d+\)|M\d+\b|[^—]+\s+\(M\d+\),)", plain))


def inject(root: Path, year: int, by_date) -> int:
    changed = 0
    for page in sorted((root / str(year)).glob("W??/index.html")):
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
    aids = instrument_map()
    if len(aids) < 100:
        raise RuntimeError(f"Expected established 2026 observing aids for nearly all Messier objects; found {len(aids)}")
    for year in YEARS:
        e = events(catalog, aids, year)
        a = inject(SOURCE_SITE, year, e)
        b = inject(PUBLIC, year, e)
        print(f"{year}: standardized 110 Messier events; updated {a} source + {b} public pages")

if __name__ == "__main__":
    main()
