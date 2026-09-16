#!/usr/bin/env python3
"""Build the accepted Martz/MacRobert finder-geometry registry.

Constellation paths come from the repository's pinned IAU/Sky & Telescope
stick-figure source.  Asterism records preserve resolved member positions;
they do not invent line connections where the source defines membership only.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONSTELLATIONS = ROOT / "constellation-observance-2026.csv"
DEFAULT_ASTERISMS = ROOT / "asterism-member-coordinates.csv"
DEFAULT_OUTPUT = ROOT / "finder-geometry" / "martz-macrobert.json"

SOURCE_URL = (
    "https://raw.githubusercontent.com/dcf21/constellation-stick-figures/"
    "75d29c207bbd752023c447ddd1f9f4ff0eb47538/constellation_lines_iau.dat"
)
SOURCE_COMMIT = "75d29c207bbd752023c447ddd1f9f4ff0eb47538"


def normalized(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def read_constellation_map(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_abbr: dict[str, dict[str, str]] = {}
    for row in rows:
        name = (row.get("name") or "").strip()
        abbr = (row.get("abbr") or "").strip()
        if name and abbr:
            by_abbr.setdefault(abbr, {"name": name, "abbr": abbr})
    if len(by_abbr) != 88:
        raise RuntimeError(f"Expected 88 constellation identities, found {len(by_abbr)}")
    return sorted(by_abbr.values(), key=lambda row: row["abbr"])


def parse_vertex(raw: str) -> dict[str, object]:
    external = raw.endswith("*")
    value = raw[:-1] if external else raw
    if not value.isdigit():
        raise RuntimeError(f"Invalid Hipparcos vertex {raw!r}")
    return {"catalog": "HIP", "id": int(value), "external_to_constellation": external}


def read_figure_source(path: Path) -> dict[str, list[list[dict[str, object]]]]:
    figures: dict[str, list[list[dict[str, object]]]] = {}
    current: str | None = None
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if line.startswith("* "):
            current = line[2:].strip()
            if current in figures:
                raise RuntimeError(f"Duplicate figure section {current!r}")
            figures[current] = []
        elif line.startswith("["):
            if current is None:
                raise RuntimeError(f"Path before figure heading on line {line_number}")
            try:
                raw_path = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid figure path on line {line_number}: {line}") from exc
            if not isinstance(raw_path, list) or len(raw_path) < 2:
                raise RuntimeError(f"Figure path needs at least 2 vertices on line {line_number}")
            figures[current].append([parse_vertex(str(value)) for value in raw_path])
    if len(figures) != 89:
        raise RuntimeError(f"Expected 89 source sections, found {len(figures)}")
    return figures


def constellation_records(
    identities: list[dict[str, str]],
    figures: dict[str, list[list[dict[str, object]]]],
) -> dict[str, dict[str, object]]:
    by_normalized = {normalized(key): key for key in figures}
    records: dict[str, dict[str, object]] = {}
    for identity in identities:
        name, abbr = identity["name"], identity["abbr"]
        if abbr == "Ser":
            components = [
                {"name": "Caput", "source_key": "SerpensB", "paths": figures["SerpensB"]},
                {"name": "Cauda", "source_key": "SerpensA", "paths": figures["SerpensA"]},
            ]
            records[abbr] = {
                "name": name,
                "has_figure": True,
                "components": components,
                "paths": [path for component in components for path in component["paths"]],
            }
            continue
        source_key = by_normalized.get(normalized(name))
        if source_key is None:
            raise RuntimeError(f"No adopted figure section matches {name!r} ({abbr})")
        paths = figures[source_key]
        records[abbr] = {
            "name": name,
            "source_key": source_key,
            "has_figure": bool(paths),
            "paths": paths,
        }
    if set(records) != {row["abbr"] for row in identities}:
        raise RuntimeError("Constellation registry keys do not match the 88 adopted identities")
    no_figure = sorted(key for key, value in records.items() if not value["has_figure"])
    if no_figure != ["Men", "Mic"]:
        raise RuntimeError(f"Expected only Mensa and Microscopium without figures, found {no_figure}")
    return records


def asterism_records(path: Path) -> dict[str, dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        name = (row.get("asterism") or "").strip()
        if name:
            grouped[name].append(row)
    if len(grouped) != 25:
        raise RuntimeError(f"Expected 25 resolved asterisms, found {len(grouped)}")
    records: dict[str, dict[str, object]] = {}
    for name, members in sorted(grouped.items()):
        identifier = f"asterism-{slug(name)}"
        vertices = []
        for row in members:
            source_id = (row.get("coordinate_source_id") or "").strip()
            match = re.fullmatch(r"HIP (\d+)", source_id)
            if match is None:
                raise RuntimeError(f"{name}: unresolved Hipparcos identity {source_id!r}")
            vertices.append(
                {
                    "member": (row.get("member") or "").strip(),
                    "display_name": (row.get("resolved_object") or "").strip(),
                    "catalog": "HIP",
                    "id": int(match.group(1)),
                    "ra_h": float(row["ra_h"]),
                    "dec_deg": float(row["dec_deg"]),
                    "magnitude": float(row["mag"]),
                }
            )
        records[identifier] = {
            "name": name,
            "geometry_status": "resolved-membership-only",
            "draw_policy": "Do not infer edges; use an accepted path definition before drawing lines.",
            "members": vertices,
        }
    return records


def build(source: Path, constellations: Path, asterisms: Path) -> dict[str, object]:
    figures = read_figure_source(source)
    identities = read_constellation_map(constellations)
    try:
        asterism_source = str(asterisms.resolve().relative_to(ROOT))
    except ValueError:
        asterism_source = str(asterisms)
    return {
        "schema_version": 1,
        "system": "Martz/MacRobert",
        "provenance": {
            "constellation_source": SOURCE_URL,
            "constellation_source_commit": SOURCE_COMMIT,
            "constellation_source_note": "IAU/Sky & Telescope stick-figure dataset adopted by Star Almanack",
            "asterism_source": asterism_source,
        },
        "constellations": constellation_records(identities, figures),
        "asterisms": asterism_records(asterisms),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--constellations", type=Path, default=DEFAULT_CONSTELLATIONS)
    parser.add_argument("--asterisms", type=Path, default=DEFAULT_ASTERISMS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = build(args.source, args.constellations, args.asterisms)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"Registry is missing or stale: {args.output}")
        print(f"PASS: {args.output} is current")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote {args.output}: {len(payload['constellations'])} constellations, "
        f"{len(payload['asterisms'])} asterisms"
    )


if __name__ == "__main__":
    main()
