#!/usr/bin/env python3
"""Compute Star Almanack geometry and 2026 visibility for the 25 core asterisms.

The membership catalog remains authoritative for *which* stars define each
asterism.  This module handles only geometry and observance:

    catalog member coordinates
      -> unit vectors on the celestial sphere
      -> zero-margin spherical convex hull
      -> spherical area centroid
      -> existing Star Almanack 9 PM LAT visibility rule

For a two-member asterism there is no enclosed spherical area.  Its center is
therefore the midpoint of the minor great-circle arc joining the two members.

The polygon centroid is computed from an exact surface first moment.  A convex
spherical polygon is triangulated from an interior unit vector.  For each
spherical triangle (a,b,c), the surface-vector integral is obtained from its
oriented boundary via Stokes' theorem:

    integral_R r dOmega = 1/2 * integral_boundary (r x dr)

and a great-circle edge p->q contributes

    angle(p,q) * normalize(p x q).

Normalizing the summed first moment gives the spherical area centroid direction.
This avoids flattening RA/Dec or using a planar centroid approximation.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from compute_bayer_visibility_2026 import best_visibility, iso_date

EPS = 1.0e-12


@dataclass(frozen=True)
class SkyPoint:
    name: str
    ra_h: float
    dec_deg: float


def dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


def cross(a, b):
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )


def add(a, b):
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])


def scale(a, s):
    return (a[0]*s, a[1]*s, a[2]*s)


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    if n <= EPS:
        raise ValueError("Cannot normalize a zero vector")
    return scale(a, 1.0/n)


def to_vector(ra_h: float, dec_deg: float):
    ra = math.radians(15.0 * ra_h)
    dec = math.radians(dec_deg)
    c = math.cos(dec)
    return (c*math.cos(ra), c*math.sin(ra), math.sin(dec))


def to_radec(v):
    v = unit(v)
    ra_deg = math.degrees(math.atan2(v[1], v[0])) % 360.0
    dec_deg = math.degrees(math.asin(max(-1.0, min(1.0, v[2]))))
    return ra_deg/15.0, dec_deg


def arc_angle(a, b):
    return math.atan2(norm(cross(a, b)), dot(a, b))


def great_circle_midpoint(a, b):
    """Midpoint of the minor arc between distinct non-antipodal points."""
    if dot(a, b) <= -1.0 + 1.0e-12:
        raise ValueError("Antipodal points have no unique minor-arc midpoint")
    return unit(add(a, b))


def tangent_basis(center):
    """Return an orthonormal east/north-like basis in center's tangent plane."""
    z = (0.0, 0.0, 1.0)
    ref = z if abs(dot(center, z)) < 0.95 else (1.0, 0.0, 0.0)
    e1 = unit(cross(ref, center))
    e2 = unit(cross(center, e1))
    return e1, e2


def hemisphere_center(points):
    """Choose a stable interior direction for compact astronomical patterns."""
    s = (0.0, 0.0, 0.0)
    for p in points:
        s = add(s, p)
    c = unit(s)
    if min(dot(c, p) for p in points) <= EPS:
        raise ValueError("Member set is not contained in the selected open hemisphere")
    return c


def projected_hull_indices(points):
    """Spherical convex-hull vertices via gnomonic projection about an interior point.

    Great circles project to straight lines under gnomonic projection, so the
    ordinary 2-D convex hull is exactly the spherical convex hull as long as all
    members lie in the chosen open hemisphere.
    """
    center = hemisphere_center(points)
    e1, e2 = tangent_basis(center)
    projected = []
    for i, p in enumerate(points):
        den = dot(center, p)
        projected.append((dot(e1, p)/den, dot(e2, p)/den, i))

    # Andrew monotone chain.  Duplicate projected positions are collapsed.
    projected.sort(key=lambda t: (t[0], t[1], t[2]))
    unique = []
    for item in projected:
        if not unique or abs(item[0]-unique[-1][0]) > EPS or abs(item[1]-unique[-1][1]) > EPS:
            unique.append(item)
    if len(unique) < 3:
        return [p[2] for p in unique]

    def orient(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])

    lower = []
    for p in unique:
        while len(lower) >= 2 and orient(lower[-2], lower[-1], p) <= EPS:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(unique):
        while len(upper) >= 2 and orient(upper[-2], upper[-1], p) <= EPS:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return [p[2] for p in hull]


def triangle_area(a, b, c):
    """Unsigned solid angle of a minor spherical triangle, in steradians."""
    det = dot(a, cross(b, c))
    den = 1.0 + dot(a, b) + dot(b, c) + dot(c, a)
    return abs(2.0 * math.atan2(det, den))


def oriented_edge_moment(a, b):
    n = cross(a, b)
    nlen = norm(n)
    if nlen <= EPS:
        return (0.0, 0.0, 0.0)
    theta = math.atan2(nlen, dot(a, b))
    return scale(n, theta/nlen)


def triangle_first_moment(a, b, c):
    """Surface-vector integral over an oriented minor spherical triangle."""
    m = add(add(oriented_edge_moment(a, b), oriented_edge_moment(b, c)), oriented_edge_moment(c, a))
    return scale(m, 0.5)


def polygon_geometry(points):
    """Return (center_vector, area_sr, hull_indices, method)."""
    if len(points) == 1:
        return points[0], 0.0, [0], "single-member"
    if len(points) == 2:
        return great_circle_midpoint(points[0], points[1]), 0.0, [0, 1], "great-circle-midpoint"

    hull = projected_hull_indices(points)
    if len(hull) == 1:
        return points[hull[0]], 0.0, hull, "degenerate-single"
    if len(hull) == 2:
        return great_circle_midpoint(points[hull[0]], points[hull[1]]), 0.0, hull, "degenerate-great-circle-midpoint"

    vertices = [points[i] for i in hull]
    interior = hemisphere_center(vertices)
    total_area = 0.0
    total_moment = (0.0, 0.0, 0.0)
    for i, a in enumerate(vertices):
        b = vertices[(i+1) % len(vertices)]
        # Ensure each fan triangle has positive orientation about the interior.
        if dot(interior, cross(a, b)) < 0.0:
            a, b = b, a
        area = triangle_area(interior, a, b)
        moment = triangle_first_moment(interior, a, b)
        if dot(moment, interior) < 0.0:
            moment = scale(moment, -1.0)
        total_area += area
        total_moment = add(total_moment, moment)

    if total_area <= EPS or norm(total_moment) <= EPS:
        raise ValueError("Degenerate spherical polygon")
    return unit(total_moment), total_area, hull, "spherical-convex-hull-area-centroid"


def read_members(path: Path):
    """Read resolved member coordinates from a CSV cross-match.

    Required columns: asterism, member, ra_h, dec_deg.
    The cross-match is intentionally a separate artifact from the provenance
    YAML so catalog-coordinate choices remain inspectable.
    """
    groups = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"asterism", "member", "ra_h", "dec_deg"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
        for row in reader:
            groups.setdefault(row["asterism"], []).append(
                SkyPoint(row["member"], float(row["ra_h"]), float(row["dec_deg"]))
            )
    return groups


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("members_csv", type=Path, help="asterism member coordinate cross-match")
    parser.add_argument("output", type=Path, nargs="?", default=Path("asterism-geometry-2026.csv"))
    args = parser.parse_args()

    groups = read_members(args.members_csv)
    rows = []
    for name, members in groups.items():
        vectors = [to_vector(p.ra_h, p.dec_deg) for p in members]
        center, area_sr, hull, method = polygon_geometry(vectors)
        ra_h, dec_deg = to_radec(center)
        instant, date = best_visibility(ra_h)
        rows.append({
            "asterism": name,
            "member_count": len(members),
            "hull_member_count": len(hull),
            "hull_members": "; ".join(members[i].name for i in hull),
            "geometry_method": method,
            "centroid_ra_h": f"{ra_h:.8f}",
            "centroid_dec_deg": f"{dec_deg:.8f}",
            "area_sr": f"{area_sr:.12f}",
            "area_sq_deg": f"{area_sr * (180.0/math.pi)**2:.6f}",
            "best_instant_utc": instant.strftime("%Y-%m-%d %H:%M"),
            "best_date": date.isoformat(),
            "iso": iso_date(date),
        })
        print(f"{name:32s} RA {ra_h:10.7f}h Dec {dec_deg:+10.6f} -> {date.isoformat()} ({method})")

    if not rows:
        raise SystemExit("No asterism member coordinates found")
    fieldnames = list(rows[0].keys())
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} asterism geometry rows to {args.output}")


if __name__ == "__main__":
    main()
