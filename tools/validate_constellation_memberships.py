#!/usr/bin/env python3
"""Validate derived fixed-object constellation memberships geometrically.

The repository-owned IAU J2000 boundary snapshot is authoritative for this
check. Source catalog labels remain provenance; this validator never rewrites
them. Objects without a usable reference position are reported as unvalidated.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBJECTS_PATH = ROOT / "database" / "fixed-objects.json"
MEMBERSHIPS_PATH = ROOT / "database" / "constellation-memberships.json"
BOUNDARY_DIR = ROOT / "reference-data" / "iau-constellation-boundaries"
REPORT_PATH = ROOT / "generated" / "constellation-membership-validation.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_boundary(path: Path):
    points = []
    abbreviation = None
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3:
            raise SystemExit(f"invalid boundary row {path}:{line_number}: {raw!r}")
        hms = parts[0].split()
        if len(hms) != 3:
            raise SystemExit(f"invalid boundary RA {path}:{line_number}: {parts[0]!r}")
        h, m, s = map(float, hms)
        ra_deg = 15.0 * (h + m / 60.0 + s / 3600.0)
        dec_deg = float(parts[1])
        row_abbreviation = parts[2].upper()
        if row_abbreviation in {"SER1", "SER2"}:
            row_abbreviation = "SER"
        if abbreviation is None:
            abbreviation = row_abbreviation
        elif row_abbreviation != abbreviation:
            raise SystemExit(f"mixed constellation abbreviations in {path}")
        points.append((ra_deg, dec_deg))
    if len(points) < 3 or not abbreviation:
        raise SystemExit(f"boundary file has insufficient vertices: {path}")
    return abbreviation, points


def load_boundaries():
    grouped = {}
    files = sorted(BOUNDARY_DIR.glob("*.txt"))
    if len(files) != 89:
        raise SystemExit(f"expected 89 IAU boundary files, found {len(files)}")
    for path in files:
        abbreviation, points = parse_boundary(path)
        grouped.setdefault(abbreviation, []).append((path.name, points))
    if len(grouped) != 88:
        raise SystemExit(f"expected 88 IAU constellations, found {len(grouped)}")
    return grouped


def unwrap_ra(ra_deg, reference_deg):
    return reference_deg + ((ra_deg - reference_deg + 180.0) % 360.0) - 180.0


def on_segment(px, py, ax, ay, bx, by, eps=1e-10):
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > eps:
        return False
    return min(ax, bx) - eps <= px <= max(ax, bx) + eps and min(ay, by) - eps <= py <= max(ay, by) + eps


def point_in_polygon(ra_deg, dec_deg, vertices):
    """Ray-cast after unwrapping every RA around the tested meridian."""
    polygon = [(unwrap_ra(x, ra_deg), y) for x, y in vertices]
    px, py = ra_deg, dec_deg
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        if on_segment(px, py, xi, yi, xj, yj):
            return True
        if (yi > py) != (yj > py):
            x_intersection = (xj - xi) * (py - yi) / (yj - yi) + xi
            if px < x_intersection:
                inside = not inside
        j = i
    return inside


def geometric_constellation(ra_h, dec_deg, boundaries):
    ra_deg = (float(ra_h) * 15.0) % 360.0
    dec_deg = float(dec_deg)
    matches = []
    for abbreviation, polygons in boundaries.items():
        if any(point_in_polygon(ra_deg, dec_deg, vertices) for _, vertices in polygons):
            matches.append(abbreviation.title())
    return sorted(set(matches))


def reference_position(obj):
    candidates = []
    for record in obj.get("source_records") or []:
        facts = record.get("facts") or {}
        ra = facts.get("ra_h")
        if ra is None:
            ra = facts.get("ra")
        dec = facts.get("dec_deg")
        if dec is None:
            dec = facts.get("dec")
        try:
            ra = float(ra)
            dec = float(dec)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(ra) or not math.isfinite(dec) or not (0.0 <= ra <= 24.0) or not (-90.0 <= dec <= 90.0):
            continue
        candidates.append((record.get("source", ""), record.get("source_key", ""), ra, dec))
    if not candidates:
        return None
    source, source_key, ra, dec = candidates[0]
    return {"source": source, "source_key": source_key, "ra_h": ra, "dec_deg": dec}


def main():
    boundaries = load_boundaries()
    objects = {obj["fixed_object_id"]: obj for obj in load(OBJECTS_PATH).get("fixed_objects") or []}
    memberships = load(MEMBERSHIPS_PATH).get("constellation_memberships") or []

    checked = []
    mismatches = []
    ambiguous = []
    zero_matches = []
    multiple_matches = []
    unvalidated = []

    for membership in memberships:
        fixed_id = membership["fixed_object_id"]
        obj = objects.get(fixed_id)
        if obj is None:
            raise SystemExit(f"membership references missing fixed_object_id {fixed_id}")
        position = reference_position(obj)
        if position is None:
            unvalidated.append(fixed_id)
            continue
        matches = geometric_constellation(position["ra_h"], position["dec_deg"], boundaries)
        result = {
            "fixed_object_id": fixed_id,
            "derived_constellation": membership["constellation"],
            "geometric_constellations": matches,
            "reference_position": position,
        }
        checked.append(result)
        if not matches:
            ambiguous.append(result)
            zero_matches.append(result)
        elif len(matches) > 1:
            ambiguous.append(result)
            multiple_matches.append(result)
        elif matches[0].lower() != str(membership["constellation"]).lower():
            mismatches.append(result)

    report = {
        "schema_version": 1,
        "purpose": "Geometric validation of derived constellation memberships against the repository-owned IAU J2000 boundary snapshot.",
        "fixed_objects_source": "database/fixed-objects.json",
        "memberships_source": "database/constellation-memberships.json",
        "boundary_snapshot": "reference-data/iau-constellation-boundaries",
        "validated_count": len(checked),
        "unvalidated_count": len(unvalidated),
        "mismatch_count": len(mismatches),
        "ambiguous_boundary_count": len(ambiguous),
        "zero_match_count": len(zero_matches),
        "multiple_match_count": len(multiple_matches),
        "unvalidated_fixed_object_ids": unvalidated,
        "mismatches": mismatches,
        "zero_match_results": zero_matches,
        "multiple_match_results": multiple_matches,
        "ambiguous_boundary_results": ambiguous,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"Validated {len(checked)} memberships; {len(unvalidated)} without usable coordinates; "
        f"{len(mismatches)} mismatches; {len(ambiguous)} ambiguous boundary results "
        f"({len(zero_matches)} zero-match, {len(multiple_matches)} multiple-match)."
    )
    for result in ambiguous[:10]:
        pos = result["reference_position"]
        print(
            "AMBIGUOUS SAMPLE: "
            f"{result['fixed_object_id']} derived={result['derived_constellation']} "
            f"ra_h={pos['ra_h']} dec_deg={pos['dec_deg']} "
            f"matches={result['geometric_constellations']}"
        )
    if mismatches or ambiguous:
        raise SystemExit("IAU geometric constellation-membership validation requires review")


if __name__ == "__main__":
    main()
