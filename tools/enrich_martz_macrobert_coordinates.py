#!/usr/bin/env python3
"""Enrich accepted Martz/MacRobert HIP vertices with pinned HYG v4.1 coordinates.

This stage adds only catalog facts (RA, Dec, magnitude) to already-accepted
vertices. It never changes, adds, removes, or infers figure edges.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


HYG_COMMIT = "3bf37f4b2d5460e1278286320d1d62fab9b493c1"
HYG_URL = (
    "https://raw.githubusercontent.com/astronexus/HYG-Database/"
    f"{HYG_COMMIT}/hyg/CURRENT/hygdata_v41.csv"
)


def load_hyg(path: Path) -> dict[int, dict[str, float]]:
    stars: dict[int, dict[str, float]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            raw_hip = (row.get("hip") or "").strip()
            raw_ra = (row.get("ra") or "").strip()
            raw_dec = (row.get("dec") or "").strip()
            if not raw_hip or not raw_ra or not raw_dec:
                continue
            try:
                hip = int(float(raw_hip))
                record = {"ra_h": float(raw_ra), "dec_deg": float(raw_dec)}
                raw_mag = (row.get("mag") or "").strip()
                if raw_mag:
                    record["magnitude"] = float(raw_mag)
            except ValueError as exc:
                raise RuntimeError(f"Invalid HYG row for HIP {raw_hip!r}") from exc
            if hip in stars:
                raise RuntimeError(f"Duplicate HYG HIP identity {hip}")
            stars[hip] = record
    if not stars:
        raise RuntimeError("No Hipparcos stars loaded from HYG catalog")
    return stars


def enrich_vertex(vertex: dict, stars: dict[int, dict[str, float]], context: str) -> None:
    if vertex.get("catalog") != "HIP":
        raise RuntimeError(f"{context}: unsupported vertex catalog {vertex.get('catalog')!r}")
    hip = vertex.get("id")
    if not isinstance(hip, int):
        raise RuntimeError(f"{context}: invalid HIP id {hip!r}")
    facts = stars.get(hip)
    if facts is None:
        raise RuntimeError(f"{context}: HIP {hip} is absent from pinned HYG v4.1")
    vertex.update(facts)


def enrich(payload: dict, stars: dict[int, dict[str, float]]) -> dict:
    if payload.get("system") != "Martz/MacRobert":
        raise RuntimeError("Not a Martz/MacRobert geometry registry")
    constellations = payload.get("constellations")
    if not isinstance(constellations, dict) or len(constellations) != 88:
        raise RuntimeError("Expected 88 constellation records")

    for abbr, record in constellations.items():
        for path_index, path in enumerate(record.get("paths") or [], 1):
            for vertex_index, vertex in enumerate(path, 1):
                enrich_vertex(vertex, stars, f"{abbr} path {path_index} vertex {vertex_index}")
        for subfigure in record.get("named_subfigures") or []:
            for path_index, path in enumerate(subfigure.get("paths") or [], 1):
                for vertex_index, vertex in enumerate(path, 1):
                    enrich_vertex(
                        vertex,
                        stars,
                        f"{abbr}/{subfigure.get('id')} path {path_index} vertex {vertex_index}",
                    )

    provenance = payload.setdefault("provenance", {})
    provenance["stellar_coordinate_source"] = HYG_URL
    provenance["stellar_coordinate_source_commit"] = HYG_COMMIT
    provenance["stellar_coordinate_frame"] = "HYG v4.1 catalog RA/Dec (J2000-era catalog coordinates)"
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--hyg", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.registry.read_text(encoding="utf-8"))
    stars = load_hyg(args.hyg)
    rendered = json.dumps(enrich(payload, stars), indent=2, ensure_ascii=False) + "\n"

    if args.check:
        current = args.registry.read_text(encoding="utf-8")
        if current != rendered:
            raise SystemExit(f"Coordinate enrichment is missing or stale: {args.registry}")
        print(f"PASS: {args.registry} has resolved coordinates for all drawable HIP vertices")
        return

    args.registry.write_text(rendered, encoding="utf-8")
    print(f"Enriched {args.registry} from pinned HYG v4.1")


if __name__ == "__main__":
    main()
