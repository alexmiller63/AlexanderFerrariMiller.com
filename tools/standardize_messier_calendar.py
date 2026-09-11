#!/usr/bin/env python3
"""Render Messier calendar events in the Star Almanack canonical form.

The fixed-object catalog owns Messier identity, type, constellation, magnitude,
and declination.  The fixed-sky population stage owns year-specific visibility
dates and writes them to generated/messier-visibility-YEAR.csv.  This renderer
consumes those generated dates instead of independently recalculating them.
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
from star_almanack_astronomy import declination_band, season_for
from star_almanack_objects import HTML_AID, observing_aid_for_magnitude

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
GENERATED = SRC / "generated"
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
    out: dict[str, dict[str, str]] = {}
    active = False
    for raw in FIXED.read_text(encoding="utf-8").splitlines():
        if raw == "messier:":
            active = True
            continue
        if active and raw and not raw.startswith(" "):
            break
        if not active:
            continue
        match = re.match(r"\s*-\s*\[(.*)\]\s*$", raw)
        if not match:
            continue
        row = next(csv.reader([match.group(1)], skipinitialspace=True))
        if len(row) < 9 or not re.fullmatch(r"M\d{1,3}", row[0].strip()):
            continue
        designation = row[0].strip().upper()
        source_name = row[2].strip()
        if source_name.casefold() == "null":
            source_name = ""
        edit = EDITORIAL["objects"].get(designation, {})
        accepted_name = edit.get("accepted_name", source_name)
        if accepted_name is None:
            accepted_name = ""
        preferred_name = names.preferred_messier_name(designation, accepted_name)
        object_type = edit.get(
            "editorial_type",
            EDITORIAL["type_labels"].get(row[3].strip(), row[3].strip()),
        )
        constellation = EDITORIAL["constellation_labels"].get(
            row[4].strip(), row[4].strip()
        )
        out[designation] = {
            "id": designation,
            "name": preferred_name,
            "type": object_type,
            "con": constellation,
            "dec_deg": row[6].strip(),
            "mag": row[7].strip(),
        }
    if len(out) != 110:
        raise RuntimeError(f"Expected 110 Messier objects, found {len(out)}")
    return out


def load_visibility(year: int) -> dict[str, dict[str, str]]:
    path = GENERATED / f"messier-visibility-{year}.csv"
    if not path.exists():
        raise RuntimeError(
            f"Missing {path.relative_to(ROOT)}; run populate_fixed_sky.py before Messier standardization"
        )
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_id = {row["messier"].strip().upper(): row for row in rows}
    if len(by_id) != 110:
        raise RuntimeError(
            f"Expected 110 Messier visibility rows for {year}, found {len(by_id)}"
        )
    return by_id


def label(record: dict[str, str], day: dt.date) -> str:
    head = record["id"]
    if record["name"]:
        head += f', {record["name"]}'
    head += f', {record["type"]} in {record["con"]}'

    aid = observing_aid_for_magnitude(record["mag"])
    glyph = HTML_AID[aid] if aid is not None else ""
    magnitude = record["mag"]
    visibility = " ".join(
        part for part in (glyph, f"V {magnitude}" if magnitude else "") if part
    )
    visibility_html = (
        f'<span class="visibility-magnitude">{visibility}</span>' if visibility else ""
    )

    parts = [head]
    if visibility_html:
        parts.append(visibility_html)
    parts.append(f"{declination_band(record['dec_deg'])} {season_for(day)}")
    return " — ".join(parts)


def events(catalog: dict[str, dict[str, str]], year: int):
    visibility = load_visibility(year)
    out = defaultdict(list)
    for designation in sorted(catalog, key=lambda value: int(value[1:])):
        if designation not in visibility:
            raise RuntimeError(f"Missing {designation} from generated Messier visibility for {year}")
        day = dt.date.fromisoformat(visibility[designation]["best_date"])
        out[day].append(label(catalog[designation], day))
    return out


def is_messier_event(item: str) -> bool:
    plain = re.sub(r"<[^>]+>", "", item).strip()
    return bool(
        re.match(
            r"^(?:Messier\s+\d+\s+\(M\d+\)|M\d+\b|[^—]+\s+\(M\d+\),)",
            plain,
        )
    )


def pages_for_events(root: Path, by_date) -> list[Path]:
    pages: list[Path] = []
    for iso_year in sorted({day.isocalendar().year for day in by_date}):
        pages.extend(sorted((root / str(iso_year)).glob("W??/index.html")))
    return pages


def inject(root: Path, by_date) -> int:
    changed = 0
    for page in pages_for_events(root, by_date):
        text = page.read_text(encoding="utf-8")
        original = text
        for day, labels in by_date.items():
            date_text = day.strftime("%a, %b %d, %Y")
            pattern = re.compile(
                rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)"
            )
            match = pattern.search(text)
            if not match:
                continue
            keep = (
                []
                if match.group(2) == "—"
                else [
                    item
                    for item in match.group(2).split("<br>")
                    if item and not is_messier_event(item)
                ]
            )
            keep.extend(labels)
            replacement = "<br>".join(keep) if keep else "—"
            text = text[: match.start(2)] + replacement + text[match.end(2) :]
        if text != original:
            page.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def main():
    catalog = load_catalog()
    for year in requested_years():
        by_date = events(catalog, year)
        source_changed = inject(SOURCE_SITE, by_date)
        public_changed = inject(PUBLIC, by_date)
        print(
            f"{year}: standardized 110 Messier events; "
            f"updated {source_changed} source + {public_changed} public pages"
        )


if __name__ == "__main__":
    main()
