#!/usr/bin/env python3
"""Classify fixed objects against persistent sky-region masks.

The first region implemented is the visible Milky Way.  Membership is derived
from the outermost (``ol1``) contour in the Milky Way Outline Catalog by
José R. Vieira, using the J2000 GeoJSON conversion distributed by d3-celestial.

The authoritative fixed-object catalog remains ``Historical/fixed-objects.yaml``.
Derived region membership is written to the companion catalog
``Historical/fixed-object-regions.yaml`` so future Milky Way subregions
can be added without changing the fixed-object row schemas.

No live astronomical answer is consumed.  The mask is pinned to a historical
source commit and is used only as source data for a deterministic point-in-
polygon classification.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXED_OBJECTS = ROOT / "Historical" / "fixed-objects.yaml"
OUTPUT = ROOT / "Historical" / "fixed-object-regions.yaml"
CACHE = ROOT / ".cache" / "source-data" / "milky-way-vieira-mw.json"

SOURCE_COMMIT = "fc3f358ff33c95a708d0908a84b2f5348bb445ea"
SOURCE_URL = (
    "https://raw.githubusercontent.com/ofrohn/d3-celestial/"
    f"{SOURCE_COMMIT}/data/mw.json"
)
SOURCE_NAME = "José R. Vieira Milky Way Outline Catalog via d3-celestial"
SOURCE_FEATURE = "ol1"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixed-objects", type=Path, default=FIXED_OBJECTS)
    p.add_argument("--output", type=Path, default=OUTPUT)
    p.add_argument("--mask", type=Path, default=CACHE)
    p.add_argument(
        "--offline",
        action="store_true",
        help="refuse network access; the pinned mask must already exist",
    )
    return p.parse_args()


def ensure_mask(path: Path, offline: bool) -> Path:
    if path.exists():
        return path
    if offline:
        raise FileNotFoundError(f"Milky Way mask not found: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading pinned Milky Way mask: {SOURCE_URL}")
    with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
        payload = response.read()
    path.write_bytes(payload)
    return path


def load_outer_milky_way(mask_path: Path) -> list[list[list[float]]]:
    data = json.loads(mask_path.read_text(encoding="utf-8"))
    for feature in data.get("features", []):
        if feature.get("id") != SOURCE_FEATURE:
            continue
        geometry = feature.get("geometry", {})
        if geometry.get("type") != "MultiPolygon":
            raise ValueError(
                f"Expected {SOURCE_FEATURE!r} to be MultiPolygon; "
                f"got {geometry.get('type')!r}"
            )
        return geometry["coordinates"]
    raise ValueError(f"Feature {SOURCE_FEATURE!r} not found in {mask_path}")


def ra_hours_to_geojson_lon(ra_h: float) -> float:
    """Convert J2000 RA hours to d3-celestial's GeoJSON longitude convention."""
    lon = (float(ra_h) * 15.0) % 360.0
    return lon - 360.0 if lon > 180.0 else lon


def unwrap_ring(ring: Iterable[Iterable[float]], query_lon: float) -> list[tuple[float, float]]:
    """Unwrap longitudes continuously around the query point.

    This prevents a ring crossing ±180° from being interpreted as a line across
    the whole map by the planar ray-casting test.
    """
    pts = [(float(p[0]), float(p[1])) for p in ring]
    if not pts:
        return []

    first_lon = pts[0][0]
    while first_lon - query_lon > 180.0:
        first_lon -= 360.0
    while first_lon - query_lon < -180.0:
        first_lon += 360.0

    out = [(first_lon, pts[0][1])]
    previous = first_lon
    for lon, lat in pts[1:]:
        while lon - previous > 180.0:
            lon -= 360.0
        while lon - previous < -180.0:
            lon += 360.0
        out.append((lon, lat))
        previous = lon
    return out


def point_on_segment(
    x: float, y: float, ax: float, ay: float, bx: float, by: float, eps: float = 1e-10
) -> bool:
    cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
    if abs(cross) > eps:
        return False
    return (
        min(ax, bx) - eps <= x <= max(ax, bx) + eps
        and min(ay, by) - eps <= y <= max(ay, by) + eps
    )


def point_in_ring(lon: float, lat: float, ring: Iterable[Iterable[float]]) -> bool:
    pts = unwrap_ring(ring, lon)
    if len(pts) < 3:
        return False

    # Move the query longitude into the same unwrapped neighborhood as the ring.
    center = sum(p[0] for p in pts) / len(pts)
    x = lon
    while x - center > 180.0:
        x -= 360.0
    while x - center < -180.0:
        x += 360.0
    y = lat

    inside = False
    j = len(pts) - 1
    for i, (xi, yi) in enumerate(pts):
        xj, yj = pts[j]
        if point_on_segment(x, y, xi, yi, xj, yj):
            return True
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def point_in_multipolygon(
    lon: float, lat: float, multipolygon: list[list[list[float]]]
) -> bool:
    """GeoJSON MultiPolygon membership including polygon holes."""
    for polygon in multipolygon:
        if not polygon:
            continue
        outer, *holes = polygon
        if point_in_ring(lon, lat, outer) and not any(
            point_in_ring(lon, lat, hole) for hole in holes
        ):
            return True
    return False


def table_rows(catalog: dict[str, Any], table: str) -> list[dict[str, Any]]:
    columns = catalog["schema"][table]
    rows = []
    for raw in catalog.get(table, []):
        if len(raw) != len(columns):
            raise ValueError(
                f"{table} row has {len(raw)} values but schema has {len(columns)}: {raw!r}"
            )
        rows.append(dict(zip(columns, raw)))
    return rows


def object_key(table: str, row: dict[str, Any]) -> str:
    if table == "messier":
        return str(row["id"])
    if table == "bayer":
        return f"{row['bayer']} {row['con']}"
    if table == "special":
        return str(row["id"])
    if table == "component":
        return f"{row['bayer']} {row['con']} {row['component']}"
    raise KeyError(table)


def classify(catalog: dict[str, Any], mask: list[list[list[float]]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": 1,
        "epoch": "J2000",
        "region_models": {
            "milky_way": {
                "source": SOURCE_NAME,
                "source_commit": SOURCE_COMMIT,
                "source_feature": SOURCE_FEATURE,
                "definition": "inside the outermost visible Milky Way contour",
            }
        },
        "objects": {},
    }

    for table in ("messier", "bayer", "special", "component"):
        classified: dict[str, Any] = {}
        for row in table_rows(catalog, table):
            key = object_key(table, row)
            lon = ra_hours_to_geojson_lon(float(row["ra_h"]))
            lat = float(row["dec_deg"])
            inside = point_in_multipolygon(lon, lat, mask)
            classified[key] = {
                "milky_way": {
                    "inside": bool(inside),
                    "regions": [],
                }
            }
        result["objects"][table] = classified
    return result


def count_memberships(result: dict[str, Any]) -> tuple[int, int]:
    total = inside = 0
    for table in result["objects"].values():
        for entry in table.values():
            total += 1
            inside += int(entry["milky_way"]["inside"])
    return total, inside


def main() -> int:
    args = parse_args()
    catalog = yaml.safe_load(args.fixed_objects.read_text(encoding="utf-8"))
    mask_path = ensure_mask(args.mask, args.offline)
    mask = load_outer_milky_way(mask_path)
    result = classify(catalog, mask)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(result, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )

    total, inside = count_memberships(result)
    print(f"Classified {total} fixed objects; {inside} are inside the Milky Way mask.")

    # Human-readable spot check for the motivating example when Sirius is present.
    sirius = result["objects"].get("bayer", {}).get("α CMa")
    if sirius is not None:
        print(f"Sirius (α CMa): in_milky_way={sirius['milky_way']['inside']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
