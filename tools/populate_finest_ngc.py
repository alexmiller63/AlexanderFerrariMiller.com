#!/usr/bin/env python3
"""Populate Finest NGC-only observing events into requested or discovered Almanack years.

Precedence is Messier -> Caldwell -> Finest NGC. Finest NGC objects already
represented by Messier or Caldwell are not emitted a second time. Caldwell
cross-membership is rendered by populate_caldwell.py.
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
CATALOG = SRC / "finest-ngc-catalog.csv"
CALDWELL = SRC / "finest-ngc-caldwell-overlap.csv"

CONSTELLATIONS = {
    "And":"Andromeda", "Aqr":"Aquarius", "Ari":"Aries", "Aur":"Auriga", "Boo":"Boötes", "CMa":"Canis Major",
    "Cam":"Camelopardalis", "Cas":"Cassiopeia", "Cet":"Cetus", "Com":"Coma Berenices", "Crv":"Corvus",
    "CVn":"Canes Venatici", "Cyg":"Cygnus", "Dra":"Draco", "Eri":"Eridanus", "Gem":"Gemini", "Her":"Hercules",
    "Hya":"Hydra", "Leo":"Leo", "LMi":"Leo Minor", "Mon":"Monoceros", "Ori":"Orion", "Peg":"Pegasus",
    "Per":"Perseus", "Pup":"Puppis", "Scl":"Sculptor", "Sex":"Sextans", "Sgr":"Sagittarius", "Tau":"Taurus",
    "UMa":"Ursa Major", "Vir":"Virgo",
}
TYPE_LABELS = {
    "OC":"open cluster", "GC":"globular cluster", "PN":"planetary nebula", "EN":"emission nebula",
    "RN":"reflection nebula", "E/RN":"emission/reflection nebula", "Gal":"galaxy",
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
        if root.exists():
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


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def visibility_rows(catalog: list[dict[str, str]], year: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in catalog:
        record = dict(row)
        instant, day = best_visibility(float(record["ra_h"]), year)
        record["best_instant_utc"] = instant.strftime("%Y-%m-%d %H:%M")
        record["best_date"] = day.isoformat()
        record["iso"] = iso_label(day)
        out.append(record)
    return out


def write_visibility(data: list[dict[str, str]], year: int) -> None:
    path = SRC / "generated" / f"finest-ngc-visibility-{year}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def label(record: dict[str, str]) -> str:
    catalog = record["catalog"].strip()
    name = record.get("name", "").strip()
    object_type = TYPE_LABELS.get(record.get("type", "").strip(), "deep-sky object")
    constellation_code = record.get("con", "").strip()
    constellation = CONSTELLATIONS.get(constellation_code, constellation_code)
    head = f"{catalog}, {name}, {object_type} in {constellation}" if name else f"{catalog}, {object_type} in {constellation}"

    day = dt.date.fromisoformat(record["best_date"])
    magnitude = record.get("mag", "").strip()
    observing = f"{TELESCOPE_GLYPH} V {magnitude}" if magnitude else TELESCOPE_GLYPH
    return (
        f"{head} — {observing} — Finest NGC — "
        f"{declination_band(record['dec_deg'])} {season_for(day)}"
    )


def events_for(data: list[dict[str, str]]) -> dict[dt.date, list[str]]:
    events: dict[dt.date, list[str]] = defaultdict(list)
    for record in data:
        events[dt.date.fromisoformat(record["best_date"])].append(label(record))
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
            date_text = day.strftime("%a, %b %d, %Y").replace(" 0", " ")
            pattern = re.compile(
                rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)"
            )
            match = pattern.search(text)
            if not match:
                continue
            keep = [] if match.group(2) == "—" else [item for item in match.group(2).split("<br>") if item]
            for item in labels:
                designation = item.split(",", 1)[0]
                keep = [
                    existing
                    for existing in keep
                    if not (
                        "Finest NGC" in existing
                        and re.search(rf"\b{re.escape(designation)}\b", existing)
                    )
                ]
                keep.append(item)
            text = text[: match.start(2)] + ("<br>".join(keep) if keep else "—") + text[match.end(2) :]
        if text != original:
            page.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def main() -> None:
    catalog = rows(CATALOG)
    overlap = {row["finest_ngc"] for row in rows(CALDWELL)}
    unique = [row for row in catalog if row["finest_ngc"] not in overlap]
    if len(overlap) != 33:
        raise RuntimeError(f"Expected 33 Caldwell overlaps, found {len(overlap)}")

    years = requested_years()
    if not years:
        raise RuntimeError("No generated Almanack years found")

    for year in years:
        data = visibility_rows(unique, year)
        write_visibility(data, year)
        events = events_for(data)
        source_changed = inject(SOURCE_SITE, events)
        public_changed = inject(PUBLIC, events)
        print(
            f"{year}: {len(data)} Finest NGC physical rows after Caldwell precedence; "
            f"updated {source_changed} source + {public_changed} public pages"
        )


if __name__ == "__main__":
    main()
