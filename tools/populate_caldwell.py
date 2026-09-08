#!/usr/bin/env python3
"""Populate Caldwell observing events into every generated Star Almanack year.

The Caldwell catalog is permanent fixed-sky infrastructure. Any year that has
weekly pages under almanack/YYYY or Star-Almanack-Repo/site/YYYY is discovered
automatically and receives C1-C109 using the same 9 PM LApST visibility rule
used for Messier and the other fixed-sky objects.
"""
from __future__ import annotations

import csv
import datetime as dt
import importlib.util
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
PUBLIC = ROOT / "almanack"
SOURCE_SITE = SRC / "site"
CATALOG = SRC / "caldwell-catalog.csv"

spec = importlib.util.spec_from_file_location("fixedsky", ROOT / "tools" / "populate_2025_2027_fixed_sky.py")
fixed = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(fixed)

CONSTELLATIONS = {
    "And":"Andromeda", "Aps":"Apus", "Aqr":"Aquarius", "Ara":"Ara", "Aur":"Auriga",
    "Boo":"Boötes", "CMa":"Canis Major", "Cam":"Camelopardalis", "Car":"Carina",
    "Cas":"Cassiopeia", "Cen":"Centaurus", "Cep":"Cepheus", "Cet":"Cetus", "Cha":"Chamaeleon",
    "Cir":"Circinus", "Cnc":"Cancer", "Col":"Columba", "Com":"Coma Berenices", "CrA":"Corona Australis",
    "Cru":"Crux", "Crv":"Corvus", "CVn":"Canes Venatici", "Cyg":"Cygnus", "Del":"Delphinus",
    "Dor":"Dorado", "Dra":"Draco", "For":"Fornax", "Gem":"Gemini", "Hor":"Horologium",
    "Hya":"Hydra", "Lac":"Lacerta", "Leo":"Leo", "Lyn":"Lynx", "Mon":"Monoceros",
    "Mus":"Musca", "Nor":"Norma", "Pav":"Pavo", "Peg":"Pegasus", "Per":"Perseus",
    "Pup":"Puppis", "Sco":"Scorpius", "Scl":"Sculptor", "Sex":"Sextans", "Sgr":"Sagittarius",
    "Tau":"Taurus", "TrA":"Triangulum Australe", "Tuc":"Tucana", "Vel":"Vela", "Vir":"Virgo",
    "Vul":"Vulpecula",
}

TYPE_LABELS = {
    "OC":"open cluster", "GC":"globular cluster", "PN":"planetary nebula", "BN":"bright nebula",
    "DN":"dark nebula", "SN":"supernova remnant", "IG":"irregular galaxy", "SG":"spiral galaxy",
    "SaG":"spiral galaxy", "SbG":"spiral galaxy", "ScG":"spiral galaxy", "SdG":"spiral galaxy",
    "SBG":"barred spiral galaxy", "SBbG":"barred spiral galaxy", "SBcG":"barred spiral galaxy",
    "E4G":"elliptical galaxy", "E6G":"elliptical galaxy", "dE4G":"dwarf elliptical galaxy",
    "dE0G":"dwarf elliptical galaxy", "PecG":"peculiar galaxy", "SeyfertG":"Seyfert galaxy",
}

# The Almanack owns its observing glyph artwork. Do not substitute an emoji.
TELESCOPE_GLYPH = (
    '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/telescope.svg" '
    'alt="Telescope" aria-label="Telescope" style="height:1.15em;width:auto;vertical-align:-.18em">'
)


def years_present() -> tuple[int, ...]:
    years: set[int] = set()
    for root in (PUBLIC, SOURCE_SITE):
        if not root.exists():
            continue
        for p in root.iterdir():
            if p.is_dir() and re.fullmatch(r"20\d{2}", p.name) and any(p.glob("W??/index.html")):
                years.add(int(p.name))
    return tuple(sorted(years))


def read_catalog() -> list[dict[str, str]]:
    with CATALOG.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 109:
        raise RuntimeError(f"Caldwell catalog must contain 109 rows; found {len(rows)}")
    expected = {f"C{i}" for i in range(1, 110)}
    actual = {r["caldwell"] for r in rows}
    if actual != expected:
        raise RuntimeError("Caldwell catalog identifiers are incomplete or duplicated")
    return rows


def visibility_rows(rows: list[dict[str, str]], year: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        r = dict(row)
        instant, day = fixed.best_visibility(float(r["ra_h"]), year)
        r["best_instant_utc"] = instant.strftime("%Y-%m-%d %H:%M")
        r["best_date"] = day.isoformat()
        r["iso"] = fixed.iso_label(day)
        out.append(r)
    return out


def write_visibility(rows: list[dict[str, str]], year: int) -> None:
    path = SRC / "generated" / f"caldwell-visibility-{year}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def calendar_label(r: dict[str, str]) -> str:
    cid = r["caldwell"]
    name = r.get("name", "").strip()
    obj_type = TYPE_LABELS.get(r.get("type", "").strip(), "deep-sky object")
    constellation = CONSTELLATIONS.get(r.get("con", "").strip(), r.get("con", "").strip())
    # Catalog identity belongs first: C4, Iris Nebula, bright nebula in Cepheus.
    head = f"{cid}, {name}, {obj_type} in {constellation}" if name else f"{cid}, {obj_type} in {constellation}"
    day = dt.date.fromisoformat(r["best_date"])
    band = fixed.declination_band(r["dec_deg"])
    season = fixed.season_for(day)
    mag = r.get("mag", "").strip()
    # Observing aid and magnitude are one unit: no dash between them.
    observing = f"{TELESCOPE_GLYPH} V {mag}" if mag else TELESCOPE_GLYPH
    return f"{head} — {observing} — {band} {season}"


def events_for(rows: list[dict[str, str]]) -> dict[dt.date, list[str]]:
    events: dict[dt.date, list[str]] = defaultdict(list)
    for r in rows:
        events[dt.date.fromisoformat(r["best_date"])].append(calendar_label(r))
    return events


def inject(root: Path, year: int, events: dict[dt.date, list[str]]) -> int:
    changed = 0
    for page in sorted((root / str(year)).glob("W??/index.html")):
        text = page.read_text(encoding="utf-8")
        original = text
        for day, labels in events.items():
            date_text = day.strftime("%a, %b %d, %Y").replace(" 0", " ")
            pat = re.compile(rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)")
            m = pat.search(text)
            if not m:
                continue
            keep = [] if m.group(2) == "—" else [x for x in m.group(2).split("<br>") if x]
            cid = re.search(r"\bC\d{1,3}\b", labels[0]) if labels else None
            for label in labels:
                label_cid = re.match(r"(C\d{1,3}),", label)
                if label_cid:
                    token = label_cid.group(1)
                    # Remove any prior Caldwell rendering, including the older
                    # name-first and "Caldwell N (CN)" forms.
                    keep = [x for x in keep if not re.search(rf"(?:^|\(|\b){re.escape(token)}(?:\)|,|\b)", x)]
                keep.append(label)
            text = text[:m.start(2)] + ("<br>".join(keep) if keep else "—") + text[m.end(2):]
        if text != original:
            page.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def main() -> None:
    catalog = read_catalog()
    years = years_present()
    if not years:
        raise RuntimeError("No generated Almanack years found")
    for year in years:
        rows = visibility_rows(catalog, year)
        write_visibility(rows, year)
        source_changed = inject(SOURCE_SITE, year, events_for(rows))
        public_changed = inject(PUBLIC, year, events_for(rows))
        print(f"{year}: Caldwell C1-C109; updated {source_changed} source + {public_changed} public pages")


if __name__ == "__main__":
    main()
