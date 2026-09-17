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
SOURCE_ROOT = ROOT
CANONICAL_ROOT = SOURCE_ROOT / "descriptors"
PUBLIC_ROOT = ROOT / "almanack" / "descriptors"
FIGURE_SOURCE = SOURCE_ROOT / "constellation-figures.json"
ASTERISM_SOURCE = SOURCE_ROOT / "asterisms-core-25.yaml"
STAR_HOP_SOURCE = SOURCE_ROOT / "guiding-star-hops.json"

BAYER_WORDS = {
    "Alp": "Alpha", "Bet": "Beta", "Gam": "Gamma", "Del": "Delta",
    "Eps": "Epsilon", "Zet": "Zeta", "Eta": "Eta", "The": "Theta",
    "Iot": "Iota", "Kap": "Kappa", "Lam": "Lambda", "Mu": "Mu",
    "Nu": "Nu", "Xi": "Xi", "Omi": "Omicron", "Pi": "Pi",
    "Rho": "Rho", "Sig": "Sigma", "Tau": "Tau", "Ups": "Upsilon",
    "Phi": "Phi", "Chi": "Chi", "Psi": "Psi", "Ome": "Omega",
}

# Genitives needed by the preserved 25-asterism membership catalog. Proper
# names remain the primary match; these aliases cover catalogued Bayer names.
CONSTELLATION_GENITIVES = {
    "Aqr": "Aquarii", "Boo": "Bootis", "Car": "Carinae", "Cas": "Cassiopeiae",
    "Cen": "Centauri", "Cet": "Ceti", "Cru": "Crucis", "CVn": "Canum Venaticorum",
    "Cyg": "Cygni", "Her": "Herculis", "Leo": "Leonis", "Ori": "Orionis",
    "Peg": "Pegasi", "Psc": "Piscium", "Sco": "Scorpii", "Sgr": "Sagittarii",
    "Tau": "Tauri", "UMa": "Ursae Majoris", "UMi": "Ursae Minoris",
    "Vel": "Velorum", "Vir": "Virginis", "Vul": "Vulpeculae",
}

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
    """Return a descriptor link relative to an Almanack weekly page."""
    return f"../../descriptors/{descriptor_id}.json"


def descriptor_self_reference(descriptor_id: str) -> str:
    """Return the portable self-reference stored in a descriptor record."""
    return f"./{descriptor_id}.json"


def _base(descriptor_id: str, kind: str, name: str, summary: str) -> dict:
    return {
        "schema_version": 1,
        "id": descriptor_id,
        "type": kind,
        "name": name,
        "summary": summary,
        "representation": {
            "machine": descriptor_self_reference(descriptor_id),
            "human_source": "summary",
        },
    }


def _figure_catalog() -> dict:
    if not FIGURE_SOURCE.exists():
        return {}
    return json.loads(FIGURE_SOURCE.read_text(encoding="utf-8"))


def _core_asterisms() -> list[dict]:
    """Read the fields needed from the dependency-free core YAML catalog."""
    records: list[dict] = []
    current: dict | None = None
    for raw in ASTERISM_SOURCE.read_text(encoding="utf-8").splitlines():
        if raw.startswith("  - name: "):
            if current is not None:
                records.append(current)
            current = {"name": raw.split(":", 1)[1].strip()}
        elif current is not None and raw.startswith("    status: "):
            current["status"] = raw.split(":", 1)[1].strip()
        elif current is not None and raw.startswith("    members: ["):
            body = raw.split("[", 1)[1].rsplit("]", 1)[0]
            current["members"] = [item.strip() for item in body.split(",") if item.strip()]
        elif current is not None and raw.startswith("    source: "):
            current["source"] = raw.split(":", 1)[1].strip()
        elif current is not None and raw.startswith("    source_url: "):
            current["source_url"] = raw.split(":", 1)[1].strip()
    if current is not None:
        records.append(current)
    resolved = [record for record in records if record.get("status") == "resolved" and record.get("members")]
    if len(resolved) != 28:
        raise RuntimeError(f"Expected 28 resolved core asterisms, found {len(resolved)}")
    return resolved


def _star_hops() -> list[dict]:
    document = json.loads(STAR_HOP_SOURCE.read_text(encoding="utf-8"))
    if document.get("selection_policy") != "curated-established-routes-only":
        raise RuntimeError("Guiding star-hop catalog must require curated established routes")
    routes = document.get("routes")
    if not isinstance(routes, list):
        raise RuntimeError("Guiding star-hop catalog has no routes list")
    for route in routes:
        provenance = route.get("provenance")
        if not isinstance(provenance, dict):
            raise RuntimeError(f"Star-hop route {route.get('id')} has no provenance")
        if provenance.get("source_role") != "verification":
            raise RuntimeError(f"Star-hop route {route.get('id')} must use its source for verification")
        if provenance.get("supports") != "star-hop-method":
            raise RuntimeError(f"Star-hop route {route.get('id')} has ambiguous source support")
        if route.get("instruction_authorship") != "Star Almanack original wording":
            raise RuntimeError(f"Star-hop route {route.get('id')} must identify its instruction authorship")
    return routes


def _star_aliases(star: dict | None, name: str) -> set[str]:
    aliases = {name.casefold()}
    if star:
        word = BAYER_WORDS.get(star.get("bayer"))
        genitive = CONSTELLATION_GENITIVES.get(star.get("con"))
        if word and genitive:
            aliases.add(f"{word} {genitive}".casefold())
    return aliases


def _guiding_asterisms(
    star: dict | None,
    name: str,
    hops: list[dict],
    *,
    include_memberships: bool = True,
) -> list[dict]:
    aliases = _star_aliases(star, name)
    guides = []
    catalog = _core_asterisms()
    if include_memberships:
        for record in catalog:
            if not any(member.casefold() in aliases for member in record["members"]):
                continue
            guides.append({
                "id": f"asterism-{slugify(record['name'])}",
                "name": record["name"],
                "relationship": "visual-member",
                "provenance": {
                    "source": record.get("source"),
                    "source_url": record.get("source_url"),
                    "source_role": "verification",
                    "supports": "visual-membership",
                },
            })
    known = {guide["name"] for guide in guides}
    steps = {str(step).casefold() for hop in hops for step in hop.get("steps", [])}
    for record in catalog:
        if record["name"].casefold() not in steps or record["name"] in known:
            continue
        route_ids = [
            str(hop["id"])
            for hop in hops
            if record["name"].casefold()
            in {str(step).casefold() for step in hop.get("steps", [])}
        ]
        guides.append({
            "id": f"asterism-{slugify(record['name'])}",
            "name": record["name"],
            "relationship": "star-hop-anchor",
            "relationship_route_ids": route_ids,
            "provenance": {
                "source": record.get("source"),
                "source_url": record.get("source_url"),
                "source_role": "verification",
                "supports": "asterism-definition",
            },
        })
    return guides


def _guiding_star_hops(name: str, target_type: str = "star") -> list[dict]:
    return [
        dict(route) for route in _star_hops()
        if route.get("target_type") == target_type and route.get("target") == name
    ]


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
    hops = _guiding_star_hops(catalog_name, "deep-sky-object")
    if hops:
        record["guiding_asterisms"] = _guiding_asterisms(
            None, catalog_name, hops, include_memberships=False
        )
        record["star_hops"] = hops
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
        hops = _guiding_star_hops(name)
        guides = _guiding_asterisms(star, name, hops)
        if guides:
            record["guiding_asterisms"] = guides
        if hops:
            record["star_hops"] = hops
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
            record["constellation"] = constellation_names.get(con, con)
            if asterism:
                record["members"] = asterism.get("members", [])
                record["source"] = asterism.get("source")
                record["source_url"] = asterism.get("source_url")
            add(record)

    for abbreviation in constellation_names:
        if any(
            record.get("constellation_abbreviation") == abbreviation
            for record in records
        ):
            add_constellation(abbreviation)

    return records


def render_human_summary(record: dict) -> str:
    """Return concise human-readable prose derived from a descriptor record."""
    name = html.escape(record.get("name", "descriptor"))
    summary = html.escape(record.get("summary", ""))
    return f"<strong>{name}</strong>: {summary}"


def write_descriptor(record: dict) -> Path:
    """Write one canonical and one public descriptor JSON record."""
    descriptor_id = record["id"]
    CANONICAL_ROOT.mkdir(parents=True, exist_ok=True)
    PUBLIC_ROOT.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    canonical = CANONICAL_ROOT / f"{descriptor_id}.json"
    public = PUBLIC_ROOT / f"{descriptor_id}.json"
    canonical.write_text(payload, encoding="utf-8")
    public.write_text(payload, encoding="utf-8")
    return canonical
