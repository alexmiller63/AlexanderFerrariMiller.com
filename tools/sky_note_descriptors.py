#!/usr/bin/env python3
"""Machine-readable descriptor support for Star Almanack Sky Notes.

JSON descriptor records are the source of truth for descriptor presentation.
Human-readable prose and Sky Note links are derived from these records.
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
            "constellation used by Star Almanack to organize fixed-sky objects and finder geometry",
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

    # Concepts fill out the descriptor layer without inventing weak astronomical objects.
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


def _linked_name(record: dict) -> str:
    return (
        f'<a class="descriptor-link" href="{html.escape(descriptor_href(record["id"]), quote=True)}" '
        f'type="application/json">{html.escape(record["name"], quote=False)}</a>'
    )


def human_sentence(record: dict) -> str:
    """Render useful prose strictly from fields in the machine-readable record."""
    name = _linked_name(record)
    kind = record.get("type")

    if kind == "star":
        constellation = record.get("constellation")
        magnitude = record.get("representative_visual_magnitude")
        details = []
        if constellation:
            details.append(f"in {html.escape(str(constellation))}")
        if magnitude is not None:
            details.append(f"with representative visual magnitude {magnitude:g}")
        tail = " ".join(details)
        return f"{name} is a bright fixed-sky reference{' ' + tail if tail else ''}."

    if kind == "constellation":
        figure = record.get("figure")
        if figure:
            paths = figure.get("figure_paths") or []
            return (
                f"{name} uses the preserved Martz/MacRobert stick figure in Star Almanack"
                f" ({len(paths)} figure path{'s' if len(paths) != 1 else ''})."
            )
        return f"{name} is used to organize the week’s fixed-sky objects and finder geometry."

    if kind == "asterism":
        members = record.get("members") or []
        if members:
            shown = ", ".join(html.escape(str(member)) for member in members[:5])
            extra = " and others" if len(members) > 5 else ""
            return f"{name} is an observer-facing asterism defined by {shown}{extra}."
        return f"{name} is an observer-facing star pattern preserved separately from the constellation figure."

    if kind == "deep-sky-object":
        object_type = html.escape(str(record.get("object_type", "deep-sky object")))
        constellation = record.get("constellation")
        where = f" in {html.escape(str(constellation))}" if constellation else ""
        return f"{name} is a {object_type}{where} selected as a fixed-sky target for this week."

    if kind == "planet":
        return f"{name} is tracked in the weekly ephemeris and Planet Finder as part of the Solar-System context."

    return f"{name} means {html.escape(str(record.get('summary', 'a Star Almanack observing concept')))}."


def decorate_note_html(rendered_html: str, records: list[dict]) -> str:
    """Render 3–4 substantive descriptor sentences plus 5–6 direct JSON links."""
    decorated = rendered_html

    # Prefer actual sky objects and geometry for prose. Concepts are fallback only.
    priority = {
        "deep-sky-object": 0,
        "star": 1,
        "asterism": 2,
        "constellation": 3,
        "planet": 4,
        "observing-concept": 5,
    }
    ordered = sorted(enumerate(records), key=lambda item: (priority.get(item[1].get("type"), 9), item[0]))
    prose_records = [record for _, record in ordered[:4]]
    prose_ids = {record["id"] for record in prose_records}

    # Existing mentions become direct machine-readable links without adding tiny
    # parenthetical placeholders. The richer explanation is generated below.
    for record in prose_records:
        escaped_name = html.escape(record["name"], quote=False)
        if escaped_name in decorated:
            decorated = decorated.replace(escaped_name, _linked_name(record), 1)

    if prose_records:
        sentences = " ".join(human_sentence(record) for record in prose_records)
        decorated += (
            '\n<p class="sky-note-descriptor-prose" data-sky-note-descriptor-prose="true">'
            f'<strong>Descriptor context:</strong> {sentences}</p>'
        )

    related = [record for record in records if record["id"] not in prose_ids][:6]
    if related:
        links = " · ".join(_linked_name(record) for record in related)
        decorated += (
            '\n<p class="sky-note-descriptors" data-sky-note-descriptors="true">'
            f'<strong>Related descriptors:</strong> {links}</p>'
        )
    return decorated
