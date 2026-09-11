#!/usr/bin/env python3
"""Populate Caldwell observing events into requested or discovered Star Almanack years.

The Caldwell catalog is permanent fixed-sky infrastructure. When years are
supplied on the command line, only those editions are updated. With no year
arguments, existing generated Almanack years are discovered automatically.
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
CATALOG = SRC / "caldwell-catalog.csv"
FINEST_OVERLAP = SRC / "finest-ngc-caldwell-overlap.csv"

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

TELESCOPE_GLYPH = (
    '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/telescope.svg" '
    'alt="Telescope" aria-label="Telescope" style="height:1.15em;width:auto;vertical-align:-.18em">'
)


def iso_label(day: dt.date) -> str:
    year, week, weekday = day.isocalendar()
    return f"{year}-W{week:02d}-{weekday}"


def years_present() -> tuple[int, ...]:
    years: set[int] = set()
    for root in (PUBLIC, SOURCE_SITE):
        if not root.exists():
            continue
        for path in root.iterdir():
            if path.is_dir() and re.fullmatch(r"20\d{2}", path.name) and any(path.glob("W??/index.html")):
                years.add(int(path.name))
    return tuple(sorted(years))


def requested_years() -> tuple[int, ...]:
    if len(sys.argv) == 1:
        return years_present()
    try:
        years = tuple(dict.fromkeys(int(value) for value in sys.argv[1:]))
    except ValueError as exc:
        raise SystemExit("Years must be integers, e.g. 2025 2027") from exc
    if any(year < 1 for year in years):
        raise SystemExit("Years must be positive integers")
    return years


def read_catalog() -> list[dict[str, str]]:
    with CATALOG.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 109:
        raise RuntimeError(f"Caldwell catalog must contain 109 rows; found {len(rows)}")
    expected = {f"C{i}" for i in range(1, 110)}
    actual = {row["caldwell"] for row in rows}
    if actual != expected:
        raise RuntimeError("Caldwell catalog identifiers are incomplete or duplicated")
    return rows


def finest_caldwell_ids() -> set[str]:
    with FINEST_OVERLAP.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ids = {row["caldwell"] for row in rows}
    if len(rows) != 33 or len(ids) != 33:
        raise RuntimeError("Finest NGC/Caldwell overlap must contain 33 unique Caldwell identities")
    return ids


def visibility_rows(rows: list[dict[str, str]], year: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        record = dict(row)
        instant, day = best_visibility(float(record["ra_h"]), year)
        record["best_instant_utc"] = instant.strftime("%Y-%m-%d %H:%M")
        record["best_date"] = day.isoformat()
        record["iso"] = iso_label(day)
        out.append(record)
    return out


def write_visibility(rows: list[dict[str, str]], year: int) -> None:
    path = SRC / "generated" / f"caldwell-visibility-{year}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def calendar_label(record: dict[str, str], finest_ids: set[str]) -> str:
    cid = record["caldwell"].strip()
    catalog = record.get("catalog", "").strip()
    name = record.get("name", "").strip()
    object_type = TYPE_LABELS.get(record.get("type", "").strip(), "deep-sky object")
    constellation_code = record.get("con", "").strip()
    constellation = CONSTELLATIONS.get(constellation_code, constellation_code)

    identity = [cid]
    if catalog:
        identity.append(catalog)
    if name:
        identity.append(name)
    head = ", ".join(identity) + f", {object_type} in {constellation}"

    day = dt.date.fromisoformat(record["best_date"])
    band = declination_band(record["dec_deg"])
    season = season_for(day)
    magnitude = record.get("mag", "").strip()
    observing = f"{TELESCOPE_GLYPH} V {magnitude}" if magnitude else TELESCOPE_GLYPH

    parts = [head, observing]
    if cid in finest_ids:
        parts.append("Finest NGC")
    parts.append(f"{band} {season}")
    return " — ".join(parts)


def events_for(rows: list[dict[str, str]], finest_ids: set[str]) -> dict[dt.date, list[str]]:
    events: dict[dt.date, list[str]] = defaultdict(list)
    for record in rows:
        events[dt.date.fromisoformat(record["best_date"])].append(calendar_label(record, finest_ids))
    return events


def pages_for_events(root: Path, events: dict[dt.date, list[str]]) -> list[Path]:
    pages: list[Path] = []
    for iso_year in sorted({day.isocalendar().year for day in events}):
        pages.extend(sorted((root / str(iso_year)).glob("W??/index.html")))
    return pages


def inject(root: Path, events: dict[dt.date, list[str]]) -> int:
    changed = 0
    for page in pages_for_events(root, events):
        text = page.read_text(encoding="utf-8")
        original = text
        for day, labels in events.items():
            date_text = day.strftime("%a, %b %d, %Y")
            pattern = re.compile(
                rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)"
            )
            match = pattern.search(text)
            if not match:
                continue
            keep = [] if match.group(2) == "—" else [item for item in match.group(2).split("<br>") if item]
            for label in labels:
                id_match = re.match(r"(C\d{1,3}),", label)
                if id_match:
                    token = id_match.group(1)
                    keep = [
                        item
                        for item in keep
                        if not re.search(rf"(?:^|\(|\b){re.escape(token)}(?:\)|,|\b)", item)
                    ]
                keep.append(label)
            text = text[: match.start(2)] + ("<br>".join(keep) if keep else "—") + text[match.end(2) :]
        if text != original:
            page.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def main() -> None:
    catalog = read_catalog()
    finest_ids = finest_caldwell_ids()
    years = requested_years()
    if not years:
        raise RuntimeError("No generated Almanack years found")
    for year in years:
        rows = visibility_rows(catalog, year)
        write_visibility(rows, year)
        events = events_for(rows, finest_ids)
        source_changed = inject(SOURCE_SITE, events)
        public_changed = inject(PUBLIC, events)
        print(
            f"{year}: Caldwell C1-C109; {len(finest_ids)} also Finest NGC; "
            f"updated {source_changed} source + {public_changed} public pages"
        )


if __name__ == "__main__":
    main()
