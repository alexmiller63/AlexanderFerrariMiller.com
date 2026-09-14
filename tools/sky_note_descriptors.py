#!/usr/bin/env python3
"""Machine-readable descriptor support for Star Almanack Sky Notes.

JSON descriptor records are the source of truth for descriptor presentation.
Human-readable glosses and Sky Note links are derived from these records.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Star-Almanack-Repo"
CANONICAL_ROOT = SOURCE_ROOT / "descriptors"
PUBLIC_ROOT = ROOT / "almanack" / "descriptors"
FIGURE_SOURCE = SOURCE_ROOT / "constellation-figures.json"

OBSERVING_CONCEPTS = {
    "ecliptic-longitude": {
        "name": "ecliptic longitude",
        "type": "observing-concept",
        "summary": "angular position measured along the ecliptic, used here for conservative weekly Solar-System comparisons",
    },
    "naked-eye": {
        "name": "Naked eye",
        "type": "observing-concept",
        "summary": "observing without optical aid",
    },
    "binoculars": {
        "name": "Binoculars",
        "type": "observing-concept",
        "summary": "wide-field optical aid useful for locating star fields and brighter deep-sky targets",
    },
    "small-telescope": {
        "name": "Small telescope",
        "type": "observing-concept",
        "summary": "a telescope suitable for resolving compact targets after the surrounding field is identified",
    },
    "zodiac": {
        "name": "zodiac",
        "type": "observing-concept",
        "summary": "the band of constellations along the ecliptic used to orient Solar-System objects",
    },
}


def slugify(value: str) -> str:
    value = value.lower().replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "descriptor"


def descriptor_href(descriptor_id: str) -> str:
    return f"/almanack/descriptors/{descriptor_id}.json"


def _base(descriptor_id: str, kind: str, name: str, summary: str) -> dict:
    return {
        "schema_version": 1,
        "id": descriptor_id,
        "type": kind,
        "name": name,
        "summary": summary,
        "representation": {
            "machine": descriptor_href(descriptor_id),
            "human_source": "summary",
        },
    }


def _figure_catalog() -> dict:
    if not FIGURE_SOURCE.exists():
        return {}
    return json.loads(FIGURE_SOURCE.read_text(encoding="utf-8"))


def _figure_for_abbreviation(abbreviation: str, figures: dict) -> tuple[str, dict] | tuple[None, None]:
    for name, record in figures.items():
        if record.get("constellation") == abbreviation:
            return name, record
    return None, None


def _deep_sky_descriptor(raw_name: str) -> dict:
    parts = [part.strip() for part in raw_name.split(",")]
    catalog_name = parts[0]
    object_type = parts[1] if len(parts) > 1 else "deep-sky object"
    constellation = None
    if len(parts) > 2:
        match = re.search(r"\bin\s+(.+)$", parts[2], flags=re.I)
        if match:
            constellation = match.group(1).strip()
    descriptor_id = slugify(catalog_name)
    summary = f"{object_type} selected as a weekly fixed-sky observing target"
    record = _base(descriptor_id, "deep-sky-object", catalog_name, summary)
    record["catalog_name"] = catalog_name
    record["object_type"] = object_type
    if constellation:
        record["constellation"] = constellation
    record["source_label"] = raw_name
    return record


def build_descriptors(
    fixed: list[dict],
    relations: list[dict],
    stars: list[dict],
    constellation_names: dict[str, str],
    asterisms: dict[str, dict],
) -> list[dict]:
    """Build an ordered set of relevant descriptor records for one Sky Note."""
    records: list[dict] = []
    seen: set[str] = set()
    stars_by_name = {star["name"].lower(): star for star in stars}
    figures = _figure_catalog()

    def add(record: dict | None) -> None:
        if not record:
            return
        descriptor_id = record["id"]
        if descriptor_id in seen:
            return
        seen.add(descriptor_id)
        records.append(record)

    def add_constellation(abbreviation: str | None) -> None:
        if not abbreviation:
            return
        name = constellation_names.get(abbreviation, abbreviation)
        descriptor_id = f"constellation-{slugify(name)}"
        record = _base(
            descriptor_id,
            "constellation",
            name,
            f"constellation used by Star Almanack to organize fixed-sky objects and finder geometry",
        )
        record["abbreviation"] = abbreviation
        figure_name, figure = _figure_for_abbreviation(abbreviation, figures)
        if figure:
            record["figure"] = {
                "system": "Martz/MacRobert",
                "source_name": figure_name,
                "figure_paths": figure.get("figure_paths", []),
                "magnitude_cutoff": figure.get("figure_cutoff"),
                "exceptions": figure.get("exceptions", []),
            }
            if figure.get("asterisms"):
                record["asterisms"] = figure["asterisms"]
        add(record)

    def add_star(name: str, abbreviation: str | None = None) -> None:
        star = stars_by_name.get(name.lower())
        con = abbreviation or (star.get("con") if star else None)
        constellation = constellation_names.get(con, con) if con else None
        descriptor_id = f"star-{slugify(name)}"
        summary = f"bright star{f' in {constellation}' if constellation else ''} used as a fixed-sky reference"
        record = _base(descriptor_id, "star", name, summary)
        if con:
            record["constellation_abbreviation"] = con
            record["constellation"] = constellation
        if star:
            record["position"] = {
                "ra_deg": round(star["ra_deg"], 6),
                "dec_deg": round(star["dec_deg"], 6),
                "ecliptic_longitude_deg": round(star["ecliptic_lon_deg"], 6),
                "ecliptic_latitude_deg": round(star["ecliptic_lat_deg"], 6),
            }
            record["representative_visual_magnitude"] = star["mag"]
        add(record)
        add_constellation(con)

    def add_planet(name: str) -> None:
        descriptor_id = f"planet-{slugify(name)}"
        add(_base(
            descriptor_id,
            "planet",
            name,
            "Solar-System planet tracked by the Star Almanack weekly ephemeris and Planet Finder",
        ))

    for item in fixed:
        if item.get("type") == "star":
            add_star(item["name"], item.get("constellation"))
        elif item.get("type") == "deep-sky":
            add(_deep_sky_descriptor(item["name"]))

    for relation in relations:
        add_planet(relation["planet"])
        if relation.get("other_planet"):
            add_planet(relation["other_planet"])
        if relation.get("star"):
            add_star(relation["star"], relation.get("constellation"))
        con = relation.get("constellation")
        add_constellation(con)
        if relation.get("asterism"):
            asterism = asterisms.get(con, {})
            descriptor_id = asterism.get("id", slugify(relation["asterism"]))
            record = _base(
                f"asterism-{descriptor_id}",
                "asterism",
                relation["asterism"],
                f"observer-facing star pattern in {constellation_names.get(con, con)}",
            )
            record["constellation_abbreviation"] = con
            record["members"] = list(asterism.get("members", ()))
            _, figure = _figure_for_abbreviation(con, figures)
            if figure:
                for candidate in figure.get("asterisms", []):
                    if candidate.get("name") == relation["asterism"]:
                        record["geometry"] = {
                            "system": "Star Almanack observer-facing asterism",
                            "paths": candidate.get("paths", []),
                            "label_offset": candidate.get("label_offset"),
                            "inset": candidate.get("inset", False),
                        }
                        break
            add(record)

    # These concepts guarantee that every weekly note has enough useful descriptor
    # touchpoints without inventing weak astronomical objects merely to hit a count.
    for descriptor_id in ("ecliptic-longitude", "naked-eye", "binoculars", "small-telescope", "zodiac"):
        concept = OBSERVING_CONCEPTS[descriptor_id]
        add(_base(descriptor_id, concept["type"], concept["name"], concept["summary"]))

    return records[:12]


def write_descriptor_records(records: list[dict]) -> None:
    CANONICAL_ROOT.mkdir(parents=True, exist_ok=True)
    PUBLIC_ROOT.mkdir(parents=True, exist_ok=True)
    for record in records:
        body = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
        filename = f"{record['id']}.json"
        (CANONICAL_ROOT / filename).write_text(body, encoding="utf-8")
        (PUBLIC_ROOT / filename).write_text(body, encoding="utf-8")


def decorate_note_html(rendered_html: str, records: list[dict]) -> str:
    """Add 3–4 inline human glosses plus 5–6 direct JSON descriptor links."""
    decorated = rendered_html
    inline_ids: set[str] = set()
    inline_count = 0

    for record in records:
        if inline_count >= 4:
            break
        name = record["name"]
        escaped_name = html.escape(name, quote=False)
        if escaped_name not in decorated:
            continue
        link = (
            f'<a class="descriptor-link" href="{html.escape(descriptor_href(record["id"]), quote=True)}" '
            f'type="application/json">{escaped_name}</a>'
            f' <span class="descriptor-gloss">({html.escape(record["summary"], quote=False)})</span>'
        )
        decorated = decorated.replace(escaped_name, link, 1)
        inline_ids.add(record["id"])
        inline_count += 1

    related = [record for record in records if record["id"] not in inline_ids][:6]
    if related:
        links = " · ".join(
            f'<a class="descriptor-link" href="{html.escape(descriptor_href(record["id"]), quote=True)}" '
            f'type="application/json">{html.escape(record["name"], quote=False)}</a>'
            for record in related
        )
        decorated += f'\n<p class="sky-note-descriptors"><strong>Related descriptors:</strong> {links}</p>'
    return decorated
