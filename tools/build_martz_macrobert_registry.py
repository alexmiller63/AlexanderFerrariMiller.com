#!/usr/bin/env python3
"""Build the accepted Martz/MacRobert finder-geometry registry.

Constellation paths come from the repository's pinned IAU/Sky & Telescope
stick-figure source. Asterism paths come from Star Almanack's accepted,
human-maintained observer-facing figure definitions. Renderers consume both
sets of paths and never invent line connections.
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
DEFAULT_ASTERISM_PATHS = ROOT / "asterism-figure-paths.json"
DEFAULT_SUBFIGURES = ROOT / "constellation-named-subfigures.json"
DEFAULT_OUTPUT = ROOT / "finder-geometry" / "martz-macrobert.json"

SOURCE_URL = (
    "https://raw.githubusercontent.com/dcf21/constellation-stick-figures/"
    "75d29c207bbd752023c447ddd1f9f4ff0eb47538/constellation_lines_iau.dat"
)
SOURCE_COMMIT = "75d29c207bbd752023c447ddd1f9f4ff0eb47538"

EXPECTED_ASTERISM_COUNT = 25
FIGURELESS_ASTERISMS = {"Orion's Sword"}
EXPECTED_ASTERISM_FIGURE_COUNT = (
    EXPECTED_ASTERISM_COUNT - len(FIGURELESS_ASTERISMS)
)


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
        raise RuntimeError(
            f"Expected 88 constellation identities, found {len(by_abbr)}"
        )
    return sorted(by_abbr.values(), key=lambda row: row["abbr"])


def parse_vertex(raw: str) -> dict[str, object]:
    external = raw.endswith("*")
    value = raw[:-1] if external else raw
    if not value.isdigit():
        raise RuntimeError(f"Invalid Hipparcos vertex {raw!r}")
    return {
        "catalog": "HIP",
        "id": int(value),
        "external_to_constellation": external,
    }


def read_figure_source(
    path: Path,
) -> dict[str, list[list[dict[str, object]]]]:
    figures: dict[str, list[list[dict[str, object]]]] = {}
    current: str | None = None

    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw.strip()

        if line.startswith("* "):
            current = line[2:].strip()
            if current in figures:
                raise RuntimeError(f"Duplicate figure section {current!r}")
            figures[current] = []

        elif line.startswith("["):
            if current is None:
                raise RuntimeError(
                    f"Path before figure heading on line {line_number}"
                )

            try:
                raw_path = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Invalid figure path on line {line_number}: {line}"
                ) from exc

            if not isinstance(raw_path, list) or len(raw_path) < 2:
                raise RuntimeError(
                    f"Figure path needs at least 2 vertices on line "
                    f"{line_number}"
                )

            figures[current].append(
                [parse_vertex(str(value)) for value in raw_path]
            )

    if len(figures) != 89:
        raise RuntimeError(
            f"Expected 89 source sections, found {len(figures)}"
        )

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
                {
                    "name": "Caput",
                    "source_key": "SerpensB",
                    "paths": figures["SerpensB"],
                },
                {
                    "name": "Cauda",
                    "source_key": "SerpensA",
                    "paths": figures["SerpensA"],
                },
            ]

            records[abbr] = {
                "name": name,
                "has_figure": True,
                "components": components,
                "paths": [
                    path
                    for component in components
                    for path in component["paths"]
                ],
            }
            continue

        source_key = by_normalized.get(normalized(name))

        if source_key is None:
            raise RuntimeError(
                f"No adopted figure section matches {name!r} ({abbr})"
            )

        paths = figures[source_key]

        records[abbr] = {
            "name": name,
            "source_key": source_key,
            "has_figure": bool(paths),
            "paths": paths,
        }

    if set(records) != {row["abbr"] for row in identities}:
        raise RuntimeError(
            "Constellation registry keys do not match the 88 adopted identities"
        )

    no_figure = sorted(
        key for key, value in records.items() if not value["has_figure"]
    )

    if no_figure != ["Men", "Mic"]:
        raise RuntimeError(
            "Expected only Mensa and Microscopium without figures, "
            f"found {no_figure}"
        )

    return records


def apply_named_subfigures(
    records: dict[str, dict[str, object]],
    path: Path,
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if payload.get("schema_version") != 1:
        raise RuntimeError(
            f"Unsupported named-subfigure schema in {path}"
        )

    raw_subfigures = payload.get("subfigures")

    if not isinstance(raw_subfigures, list):
        raise RuntimeError(
            f"Named-subfigure source must contain a list: {path}"
        )

    seen_ids: set[str] = set()

    for raw in raw_subfigures:
        if not isinstance(raw, dict):
            raise RuntimeError("Invalid named-subfigure record")

        identifier = raw.get("id")
        name = raw.get("name")
        abbreviation = raw.get("constellation")
        raw_paths = raw.get("paths")

        if not all(
            isinstance(value, str) and value
            for value in (identifier, name, abbreviation)
        ):
            raise RuntimeError(
                f"Incomplete named-subfigure record: {raw}"
            )

        if identifier in seen_ids:
            raise RuntimeError(
                f"Duplicate named-subfigure id {identifier!r}"
            )

        seen_ids.add(identifier)

        if abbreviation not in records:
            raise RuntimeError(
                f"{name}: unknown parent constellation {abbreviation!r}"
            )

        if raw.get("geometry_policy") != "reuse-parent-edges":
            raise RuntimeError(
                f"{name}: named subfigure must reuse parent edges"
            )

        display = raw.get("display")

        if display != {
            "role": "asterism-highlight",
            "stroke": "#59c86d",
        }:
            raise RuntimeError(
                f"{name}: named subfigure must use the approved "
                "green asterism highlight"
            )

        if not isinstance(raw_paths, list) or not raw_paths:
            raise RuntimeError(
                f"{name}: named subfigure has no paths"
            )

        parent_paths = records[abbreviation]["paths"]

        parent_edges = {
            tuple(sorted((left["id"], right["id"])))
            for parent_path in parent_paths
            for left, right in zip(parent_path, parent_path[1:])
        }

        paths = []

        for path_index, raw_path in enumerate(raw_paths, 1):
            if not isinstance(raw_path, list) or len(raw_path) < 2:
                raise RuntimeError(
                    f"{name}: path {path_index} needs at least 2 vertices"
                )

            try:
                ids = [int(vertex) for vertex in raw_path]
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"{name}: path {path_index} has a non-HIP vertex"
                ) from exc

            for left, right in zip(ids, ids[1:]):
                if tuple(sorted((left, right))) not in parent_edges:
                    raise RuntimeError(
                        f"{name}: HIP {left}–HIP {right} is not an "
                        "accepted parent edge"
                    )

            paths.append(
                [
                    {"catalog": "HIP", "id": vertex}
                    for vertex in ids
                ]
            )

        records[abbreviation].setdefault(
            "named_subfigures", []
        ).append(
            {
                "id": identifier,
                "name": name,
                "geometry_policy": "reuse-parent-edges",
                "display": display,
                "paths": paths,
            }
        )


def read_asterism_paths(
    path: Path,
) -> dict[str, list[list[str]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if payload.get("schema_version") != 1:
        raise RuntimeError(
            f"Unsupported asterism path schema in {path}"
        )

    raw_records = payload.get("asterisms")

    if (
        not isinstance(raw_records, dict)
        or len(raw_records) != EXPECTED_ASTERISM_FIGURE_COUNT
    ):
        count = len(raw_records) if isinstance(raw_records, dict) else 0
        raise RuntimeError(
            f"Expected {EXPECTED_ASTERISM_FIGURE_COUNT} "
            f"accepted asterism figures, found {count}"
        )

    records: dict[str, list[list[str]]] = {}

    for name, record in raw_records.items():
        raw_paths = (
            record.get("paths")
            if isinstance(record, dict)
            else None
        )

        if not isinstance(raw_paths, list) or not raw_paths:
            raise RuntimeError(
                f"{name}: accepted figure has no paths"
            )

        paths: list[list[str]] = []

        for index, raw_path in enumerate(raw_paths, 1):
            if not isinstance(raw_path, list) or len(raw_path) < 2:
                raise RuntimeError(
                    f"{name}: path {index} needs at least 2 vertices"
                )

            if not all(
                isinstance(vertex, str) and vertex.strip()
                for vertex in raw_path
            ):
                raise RuntimeError(
                    f"{name}: path {index} has an invalid vertex"
                )

            paths.append(
                [vertex.strip() for vertex in raw_path]
            )

        records[name] = paths

    return records


def asterism_records(
    member_path: Path,
    figure_path: Path,
) -> dict[str, dict[str, object]]:
    with member_path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        rows = list(csv.DictReader(handle))

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        name = (row.get("asterism") or "").strip()
        if name:
            grouped[name].append(row)

    if len(grouped) != EXPECTED_ASTERISM_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_ASTERISM_COUNT} resolved asterisms, "
            f"found {len(grouped)}"
        )

    accepted_paths = read_asterism_paths(figure_path)

    figureless = set(grouped) - set(accepted_paths)
    extra = set(accepted_paths) - set(grouped)

    if figureless != FIGURELESS_ASTERISMS or extra:
        raise RuntimeError(
            "Asterism figure/member mismatch: "
            f"figureless={sorted(figureless)}, "
            f"extra={sorted(extra)}"
        )

    records: dict[str, dict[str, object]] = {}

    for name, members in sorted(grouped.items()):
        identifier = f"asterism-{slug(name)}"
        vertices = []

        for row in members:
            source_id = (
                row.get("coordinate_source_id") or ""
            ).strip()

            match = re.fullmatch(r"HIP (\d+)", source_id)

            if match is None:
                raise RuntimeError(
                    f"{name}: unresolved Hipparcos identity "
                    f"{source_id!r}"
                )

            vertices.append(
                {
                    "member": (
                        row.get("member") or ""
                    ).strip(),
                    "display_name": (
                        row.get("resolved_object") or ""
                    ).strip(),
                    "catalog": "HIP",
                    "id": int(match.group(1)),
                    "ra_h": float(row["ra_h"]),
                    "dec_deg": float(row["dec_deg"]),
                    "magnitude": float(row["mag"]),
                }
            )

        if name in FIGURELESS_ASTERISMS:
            records[identifier] = {
                "name": name,
                "geometry_status": "no-figure",
                "draw_policy": (
                    "No stick figure is defined; "
                    "do not infer or draw edges."
                ),
                "members": vertices,
                "paths": [],
            }
            continue

        by_member = {
            vertex["member"]: vertex
            for vertex in vertices
        }

        used_members: set[str] = set()
        paths = []

        for path_index, accepted_path in enumerate(
            accepted_paths[name],
            1,
        ):
            resolved_path = []

            for member in accepted_path:
                vertex = by_member.get(member)

                if vertex is None:
                    raise RuntimeError(
                        f"{name}: accepted path {path_index} "
                        f"references non-member {member!r}"
                    )

                used_members.add(member)

                resolved_path.append(
                    {
                        "member": member,
                        "catalog": vertex["catalog"],
                        "id": vertex["id"],
                    }
                )

            paths.append(resolved_path)

        unused_members = sorted(
            set(by_member) - used_members
        )

        if unused_members:
            raise RuntimeError(
                f"{name}: members absent from accepted paths: "
                f"{unused_members}"
            )

        records[identifier] = {
            "name": name,
            "geometry_status": "accepted-paths",
            "draw_policy": (
                "Draw only the accepted paths; "
                "do not infer or replace edges."
            ),
            "members": vertices,
            "paths": paths,
        }

    return records


def build(
    source: Path,
    constellations: Path,
    asterisms: Path,
    asterism_paths: Path,
    subfigures: Path,
) -> dict[str, object]:
    figures = read_figure_source(source)
    identities = read_constellation_map(constellations)

    constellation_data = constellation_records(
        identities,
        figures,
    )

    apply_named_subfigures(
        constellation_data,
        subfigures,
    )

    try:
        asterism_source = str(
            asterisms.resolve().relative_to(ROOT)
        )
    except ValueError:
        asterism_source = str(asterisms)

    try:
        asterism_path_source = str(
            asterism_paths.resolve().relative_to(ROOT)
        )
    except ValueError:
        asterism_path_source = str(asterism_paths)

    try:
        subfigure_source = str(
            subfigures.resolve().relative_to(ROOT)
        )
    except ValueError:
        subfigure_source = str(subfigures)

    return {
        "schema_version": 1,
        "system": "Martz/MacRobert",
        "provenance": {
            "constellation_source": SOURCE_URL,
            "constellation_source_commit": SOURCE_COMMIT,
            "constellation_source_note": (
                "IAU/Sky & Telescope stick-figure dataset "
                "adopted by Star Almanack"
            ),
            "asterism_source": asterism_source,
            "asterism_path_source": asterism_path_source,
            "named_subfigure_source": subfigure_source,
        },
        "constellations": constellation_data,
        "asterisms": asterism_records(
            asterisms,
            asterism_paths,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--source",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--constellations",
        type=Path,
        default=DEFAULT_CONSTELLATIONS,
    )

    parser.add_argument(
        "--asterisms",
        type=Path,
        default=DEFAULT_ASTERISMS,
    )

    parser.add_argument(
        "--asterism-paths",
        type=Path,
        default=DEFAULT_ASTERISM_PATHS,
    )

    parser.add_argument(
        "--subfigures",
        type=Path,
        default=DEFAULT_SUBFIGURES,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )

    parser.add_argument(
        "--check",
        action="store_true",
    )

    args = parser.parse_args()

    payload = build(
        args.source,
        args.constellations,
        args.asterisms,
        args.asterism_paths,
        args.subfigures,
    )

    rendered = (
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )

    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8")
            != rendered
        ):
            raise SystemExit(
                f"Registry is missing or stale: {args.output}"
            )
        print(f"Registry is current: {args.output}")
        return

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        rendered,
        encoding="utf-8",
    )

    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()