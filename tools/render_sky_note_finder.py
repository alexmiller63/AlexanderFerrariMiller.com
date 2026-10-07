#!/usr/bin/env python3
"""Render Sky Notes stellar finders from accepted renderer specs.

This renderer is deliberately separate from the legacy reference-finder renderer.
It obeys the Sky Notes visual contract: blue constellation figures, green
asterisms, yellow open target circles, and no target arrows. Geometry is
consumed exactly as supplied by the generated spec; it is never inferred.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import csv
import json
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import matplotlib.pyplot as plt
from matplotlib.path import Path as MplPath
from matplotlib.transforms import Bbox

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from render_stellar_finders import greek_bayer_symbol, load_hyg, marker_area, project, spherical_center, star_index

NIGHT = "#071423"
STAR = "#f7f7f2"
TEXT = "#f3f5f7"
FIGURE_BLUE = "#5c8fe8"
ASTERISM_GREEN = "#59c86d"
TARGET_YELLOW = "#ffd84d"
BOUNDARY_WHITE = "#ffffff"
BOUNDARY_ROOT = REPO_ROOT / "reference-data" / "iau-constellation-boundaries"

CONSTELLATION_DISPLAY_NAMES = {
    "Capricornus": "Capricorn",
    "Delphinus": "Dolphin",
}

GREEK_SYMBOL_ORDER = "αβγδεζηθικλμνξοπρστυφχψω"
GREEK_ORDER = {symbol: rank for rank, symbol in enumerate(GREEK_SYMBOL_ORDER)}


def load_iau_boundaries():
    """Load repository-owned IAU boundary polygons keyed by abbreviation."""
    from compute_constellation_observance_2026 import CONSTELLATIONS, boundary_filenames, fetch_boundary, parse_boundary
    result = []
    for name, abbreviation in CONSTELLATIONS:
        for filename in boundary_filenames(abbreviation):
            result.append((name, abbreviation, parse_boundary(fetch_boundary(filename, BOUNDARY_ROOT))))
    return result


def constellation_for_position(ra_deg, dec_deg, boundaries):
    """Resolve a body's constellation from the same IAU snapshot drawn on the chart."""
    from compute_constellation_observance_2026 import point_in_polygon, unwrap_ra
    for name, abbreviation, points in boundaries:
        polygon = unwrap_ra(points)
        ra = ra_deg
        while ra - polygon[0][0] > 180:
            ra -= 360
        while ra - polygon[0][0] < -180:
            ra += 360
        if point_in_polygon(ra, dec_deg, polygon):
            return name, abbreviation
    raise RuntimeError(f"No IAU constellation boundary contains ({ra_deg}, {dec_deg})")


def planet_finder_title(planet, planet_constellation, reference, reference_constellation):
    if planet_constellation != reference_constellation:
        return f"{planet} in {planet_constellation}, near {reference} in {reference_constellation}"
    return f"{planet} near {reference} in {reference_constellation}"


def visible_figure_region(paths, idx, center, xmin, xmax, ymin, ymax):
    """Find the largest complete, visible loop in the constellation stick figure."""
    regions = []
    for path in paths:
        for end, ref in enumerate(path):
            if ref not in path[:end]:
                continue
            start = max(i for i in range(end) if path[i] == ref)
            loop = path[start:end + 1]
            if len(set(loop)) < 3:
                continue
            points = [project(idx[item].ra_deg, idx[item].dec_deg, *center) for item in loop]
            if any(p is None or not (xmin <= p[0] <= xmax and ymin <= p[1] <= ymax)
                   for p in points):
                continue
            area = abs(sum(a[0] * b[1] - b[0] * a[1]
                           for a, b in zip(points, points[1:])))
            regions.append((area, points))
    return max(regions, key=lambda item: item[0])[1] if regions else None


def projected_path(points, center):
    return [p for p in (project(ra, dec, *center) for ra, dec in points) if p is not None]


def path_hits_view(points, xmin, xmax, ymin, ymax):
    if any(p is not None and xmin <= p[0] <= xmax and ymin <= p[1] <= ymax for p in points):
        return True
    return any(clip_view_segment(a, b, xmin, xmax, ymin, ymax) is not None
               for a, b in zip(points, points[1:]) if a is not None and b is not None)


def clip_view_segment(start, end, xmin, xmax, ymin, ymax):
    """Clip a segment to the fixed frame, including crossings with both ends outside."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    low, high = 0.0, 1.0
    for direction, distance in ((-dx, start[0] - xmin), (dx, xmax - start[0]),
                                (-dy, start[1] - ymin), (dy, ymax - start[1])):
        if direction == 0:
            if distance < 0:
                return None
            continue
        ratio = distance / direction
        if direction < 0:
            low = max(low, ratio)
        else:
            high = min(high, ratio)
        if low > high:
            return None
    return ((start[0] + low * dx, start[1] + low * dy),
            (start[0] + high * dx, start[1] + high * dy))


def visible_context(records, idx, center, xmin, xmax, ymin, ymax):
    """Select supplied geometry only after the route has fixed the chart bounds."""
    visible = []
    for record in records:
        paths = []
        for path in record.get("paths") or []:
            if any(ref not in idx for ref in path):
                continue
            points = [project(idx[ref].ra_deg, idx[ref].dec_deg, *center) for ref in path]
            if path_hits_view(points, xmin, xmax, ymin, ymax):
                paths.append(path)
        if paths:
            visible.append(dict(record, paths=paths))
    return visible


def point_segment_distance(point, start, end):
    """Euclidean distance from a projected point to a projected line segment."""
    px, py = point
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def segment_hits_display_bbox(ax, start, end, bbox):
    """Test a data-coordinate segment against a rendered display-coordinate box."""
    x1, y1 = ax.transData.transform(start)
    x2, y2 = ax.transData.transform(end)
    left, bottom, right, top = bbox.x0, bbox.y0, bbox.x1, bbox.y1

    def inside(x, y):
        return left <= x <= right and bottom <= y <= top

    if inside(x1, y1) or inside(x2, y2):
        return True

    dx, dy = x2 - x1, y2 - y1
    edges = (
        (left, bottom, right, bottom),
        (right, bottom, right, top),
        (right, top, left, top),
        (left, top, left, bottom),
    )
    for ex1, ey1, ex2, ey2 in edges:
        edx, edy = ex2 - ex1, ey2 - ey1
        denominator = dx * edy - dy * edx
        if abs(denominator) < 1e-12:
            continue
        t = ((ex1 - x1) * edy - (ey1 - y1) * edx) / denominator
        u = ((ex1 - x1) * dy - (ey1 - y1) * dx) / denominator
        if 0 <= t <= 1 and 0 <= u <= 1:
            return True
    return False



def boundary_bbox_contains(ax, bbox, boundary_points):
    """Return True when a rendered label box stays inside a projected IAU boundary."""
    display_points = [ax.transData.transform(point) for point in boundary_points]
    if len(display_points) < 3:
        return False
    boundary_path = MplPath(display_points, closed=True)
    left, bottom, right, top = bbox.x0, bbox.y0, bbox.x1, bbox.y1
    samples = []
    for fraction in [index / 8 for index in range(9)]:
        samples.extend([
            (left + (right - left) * fraction, bottom),
            (left + (right - left) * fraction, top),
            (left, bottom + (top - bottom) * fraction),
            (right, bottom + (top - bottom) * fraction),
        ])
    if not all(boundary_path.contains_point(point) for point in samples):
        return False
    box_path = MplPath(
        [(left, bottom), (right, bottom), (right, top), (left, top)],
        closed=True,
    )
    return not boundary_path.intersects_path(box_path, filled=False)


def place_boundary_label(ax, full_label, abbreviation, point, occupied_labels,
                         boundary_points, obstacle_segments=(), color=BOUNDARY_WHITE, fontsize=10, zorder=5):
    """Place a boundary label without allowing its rendered box to leave the boundary."""
    offsets = ((0, 0), (5, 5), (7, -7), (-7, 7), (-7, -7),
               (10, 0), (0, 10), (-10, 0), (0, -10),
               (13, 7), (13, -7), (-13, 7), (-13, -7),
               (16, 0), (0, 16), (-16, 0), (0, -16))
    for label in (full_label, abbreviation):
        if not label:
            continue
        best = None
        for rank, (dx, dy) in enumerate(offsets):
            annotation = ax.annotate(
                label, point, xytext=(dx, dy), textcoords="offset points",
                fontsize=fontsize, color=color, zorder=zorder,
            )
            ax.figure.canvas.draw()
            renderer = ax.figure.canvas.get_renderer()
            bbox = annotation.get_window_extent(renderer=renderer).expanded(1.08, 1.16)
            label_hits = sum(bbox.overlaps(other) for other in occupied_labels)
            if not boundary_bbox_contains(ax, bbox, boundary_points):
                label_hits += 1
            label_hits += sum(
                segment_hits_display_bbox(ax, start, end, bbox)
                for start, end in obstacle_segments
            )
            annotation.remove()
            candidate = (label_hits, rank, dx, dy)
            if best is None or candidate < best:
                best = candidate
            if label_hits == 0:
                annotation = ax.annotate(
                    label, point, xytext=(dx, dy), textcoords="offset points",
                    fontsize=fontsize, color=color, zorder=zorder,
                )
                ax.figure.canvas.draw()
                renderer = ax.figure.canvas.get_renderer()
                occupied_labels.append(
                    annotation.get_window_extent(renderer=renderer).expanded(1.08, 1.16)
                )
                return annotation
    return None


def place_label(ax, label, point, occupied_labels, color=TEXT, fontsize=9, zorder=6,
                obstacle_segments=(), require_clear=False):
    """Place a label using its true rendered bounds for collision rejection."""
    offsets = []
    for radius in range(5, 46, 5):
        offsets.extend(((radius, 0), (-radius, 0), (0, radius), (0, -radius),
                        (radius, radius), (radius, -radius),
                        (-radius, radius), (-radius, -radius)))
    offsets.insert(0, (0, 0))
    renderer = ax.figure.canvas.get_renderer()
    best = None
    for rank, (dx, dy) in enumerate(offsets):
        annotation = ax.annotate(label, point, xytext=(dx, dy), textcoords="offset points",
                                 fontsize=fontsize, color=color, zorder=zorder)
        ax.figure.canvas.draw()
        renderer = ax.figure.canvas.get_renderer()
        bbox = annotation.get_window_extent(renderer=renderer).expanded(1.08, 1.16)
        label_hits = sum(bbox.overlaps(other) for other in occupied_labels)
        geometry_hits = sum(segment_hits_display_bbox(ax, start, end, bbox)
                            for start, end in obstacle_segments)
        score = label_hits + geometry_hits
        annotation.remove()
        candidate = (score, rank, dx, dy)
        if best is None or candidate < best:
            best = candidate
        if score == 0:
            break
    if require_clear and best[0] != 0:
        return None
    _, _, dx, dy = best
    annotation = ax.annotate(label, point, xytext=(dx, dy), textcoords="offset points",
                             fontsize=fontsize, color=color, zorder=zorder)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    occupied_labels.append(annotation.get_window_extent(renderer=renderer).expanded(1.08, 1.16))
    return annotation


def marker_obstacle_bbox(ax, point, area, linewidth, clearance_points=4):
    """Reserve a scatter circle's outer stroke plus readable space in display pixels."""
    x, y = ax.transData.transform(point)
    radius = (math.sqrt(area) / 2 + linewidth / 2 + clearance_points) * ax.figure.dpi / 72
    return Bbox.from_extents(x - radius, y - radius, x + radius, y + radius)


def place_target_label(ax, label, point, occupied_labels, obstacle_segments=(),
                       marker_radius_points=0):
    """Place the target label in the nearest genuinely clear area."""
    style = dict(
        ha="left", va="center", fontsize=10, color=TARGET_YELLOW,
        bbox=dict(facecolor=NIGHT, edgecolor="none", pad=0.8), zorder=9,
    )
    probe = ax.annotate(label, point, xytext=(14, 0), textcoords="offset points", **style)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    probe_bbox = probe.get_window_extent(renderer=renderer)
    # Annotation offsets use points; renderer bounds use display pixels.
    points_per_pixel = 72 / ax.figure.dpi
    width = probe_bbox.width * points_per_pixel
    height = probe_bbox.height * points_per_pixel
    probe.remove()

    # Search a genuine two-dimensional expanding perimeter around the target.
    # The old search coupled horizontal distance to vertical ring number, so it
    # could miss clear positions that were farther vertically but still close
    # horizontally (or vice versa).  Keep nearest-clear semantics, but explore
    # every perimeter combination before moving farther out.
    # Clearance includes the marker's outer stroke and the label background.
    marker_clearance_points = marker_radius_points + 3 if marker_radius_points else 0
    gap = max(4, marker_clearance_points + 1)
    x_step = max(width * 0.0625, 2)
    y_step = max(height * 0.25, 3)
    max_ring = 32
    offset_rings = []
    for ring in range(0, max_ring + 1):
        offsets = []
        for ix in range(0, ring + 1):
            for iy in range(-ring, ring + 1):
                if max(ix, abs(iy)) != ring:
                    continue
                for side in (-1, 1):
                    dx = gap + ix * x_step if side > 0 else -width - gap - ix * x_step
                    offsets.append((dx, iy * y_step))
        # De-duplicate the ring-zero left/right repetitions while preserving
        # deterministic search order.
        offset_rings.append(list(dict.fromkeys(offsets)))

    best = None
    anchor_x, anchor_y = ax.transData.transform(point)
    rank = 0
    for offsets in offset_rings:
        ring_best = None
        for dx, dy in offsets:
            annotation = ax.annotate(label, point, xytext=(dx, dy), textcoords="offset points", **style)
            ax.figure.canvas.draw()
            renderer = ax.figure.canvas.get_renderer()
            bbox = annotation.get_window_extent(renderer=renderer).expanded(1.08, 1.16)
            label_hits = sum(bbox.overlaps(other) for other in occupied_labels)
            geometry_hits = sum(segment_hits_display_bbox(ax, start, end, bbox)
                                for start, end in obstacle_segments)
            marker_bbox = annotation.get_bbox_patch().get_window_extent(renderer=renderer)
            marker_x = min(max(anchor_x, marker_bbox.x0), marker_bbox.x1)
            marker_y = min(max(anchor_y, marker_bbox.y0), marker_bbox.y1)
            marker_distance = math.hypot(marker_x - anchor_x, marker_y - anchor_y)
            marker_hits = marker_distance < marker_clearance_points * ax.figure.dpi / 72
            score = label_hits + geometry_hits + marker_hits
            nearest_x = min(max(anchor_x, bbox.x0), bbox.x1)
            nearest_y = min(max(anchor_y, bbox.y0), bbox.y1)
            anchor_distance = math.hypot(nearest_x - anchor_x, nearest_y - anchor_y)
            annotation.remove()
            if score == 0:
                candidate = (anchor_distance, rank, dx, dy)
                if ring_best is None or candidate < ring_best:
                    ring_best = candidate
            rank += 1
        if ring_best is not None:
            best = ring_best
            break

    if best is None:
        raise RuntimeError(f"No collision-free target-label position found for {label!r}")
    _, _, dx, dy = best
    annotation = ax.annotate(label, point, xytext=(dx, dy), textcoords="offset points", **style)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    occupied_labels.append(annotation.get_window_extent(renderer=renderer).expanded(1.08, 1.16))
    return annotation


def place_constellation_label(ax, label, point, occupied_labels, obstacle_segments=(),
                              boundary_points=None):
    """Place a constellation name by searching outward until a genuinely clear area is found."""
    probe = ax.annotate(label, point, xytext=(0, 0), textcoords="offset points",
                        fontsize=16, color=FIGURE_BLUE, zorder=5)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    width = probe.get_window_extent(renderer=renderer).width * 72 / ax.figure.dpi
    height = probe.get_window_extent(renderer=renderer).height * 72 / ax.figure.dpi
    probe.remove()

    # Search in expanding rings. The first collision-free position wins;
    # there is no constellation-specific preferred direction.
    offsets = [(0, 0)]
    for radius in range(1, 13):
        distance_x = radius * max(width * 0.5, 12)
        distance_y = radius * max(height * 0.9, 12)
        offsets.extend((
            (-distance_x, 0), (distance_x, 0),
            (0, -distance_y), (0, distance_y),
            (-distance_x, -distance_y), (-distance_x, distance_y),
            (distance_x, -distance_y), (distance_x, distance_y),
        ))

    for dx, dy in offsets:
        annotation = ax.annotate(label, point, xytext=(dx, dy), textcoords="offset points",
                                 fontsize=16, color=FIGURE_BLUE, zorder=5)
        ax.figure.canvas.draw()
        renderer = ax.figure.canvas.get_renderer()
        bbox = annotation.get_window_extent(renderer=renderer).expanded(1.08, 1.16)
        label_hits = sum(bbox.overlaps(other) for other in occupied_labels)
        if not (ax.bbox.contains(bbox.x0, bbox.y0) and ax.bbox.contains(bbox.x1, bbox.y1)):
            label_hits += 1
        if boundary_points is not None and not boundary_bbox_contains(ax, bbox, boundary_points):
            label_hits += 1
        geometry_hits = sum(segment_hits_display_bbox(ax, start, end, bbox)
                            for start, end in obstacle_segments)
        annotation.remove()
        if label_hits + geometry_hits == 0:
            annotation = ax.annotate(label, point, xytext=(dx, dy), textcoords="offset points",
                                     fontsize=16, color=FIGURE_BLUE, zorder=5)
            ax.figure.canvas.draw()
            renderer = ax.figure.canvas.get_renderer()
            occupied_labels.append(
                annotation.get_window_extent(renderer=renderer).expanded(1.08, 1.16)
            )
            return annotation
    return None


def complete_index(stars):
    idx = star_index(stars)
    for star in sorted(stars, key=lambda item: item.mag):
        if star.proper:
            idx.setdefault(star.proper, star)
    return idx


def refs_from_paths(paths):
    return {ref for path in paths for ref in path}


def identity_index(spec):
    by_ref = {}
    by_id = {}
    for identity in spec.get("fixed_object_identities") or []:
        fixed_id = identity.get("fixed_object_id")
        ref = identity.get("renderer_ref")
        if fixed_id is None or not ref:
            raise RuntimeError("Finder identity is missing fixed_object_id or renderer_ref")
        if fixed_id in by_id:
            raise RuntimeError(f"Duplicate fixed_object_id {fixed_id} in finder identities")
        by_ref[ref] = identity
        by_id[fixed_id] = identity
    return by_ref, by_id


def deep_sky_catalog_objects():
    """Load curated Messier, Caldwell, and Finest NGC finder overlays."""
    objects = []

    # fixed-objects.yaml deliberately uses a simple list schema. Parse only
    # its Messier rows here so this renderer does not add a PyYAML dependency
    # to the Artwork workflow.
    messier_columns = [
        "id", "ngc", "name", "type", "con", "ra_h", "dec_deg",
        "mag", "size_arcmin", "best", "iso",
    ]
    in_messier = False
    for raw in (REPO_ROOT / "fixed-objects.yaml").read_text(encoding="utf-8").splitlines():
        if raw == "messier:":
            in_messier = True
            continue
        if in_messier and raw and not raw.startswith(" "):
            break
        text = raw.strip()
        if not in_messier or not (text.startswith("- [") and text.endswith("]")):
            continue
        values = next(csv.reader([text[3:-1]], skipinitialspace=True))
        values = [None if value.strip().lower() == "null" else value.strip() for value in values]
        row = dict(zip(messier_columns, values))
        if row.get("ra_h") is None or row.get("dec_deg") is None:
            continue
        ngc = str(row.get("ngc") or "").strip()
        if ngc.isdigit():
            physical_key = f"NGC {int(ngc)}"
        elif re.fullmatch(r"(?:NGC|IC)\\s*\\d+", ngc, re.I):
            physical_key = ngc
        else:
            physical_key = str(row["id"])
        objects.append({
            "label": str(row["id"]),
            "ra_deg": float(row["ra_h"]) * 15.0,
            "dec_deg": float(row["dec_deg"]),
            "physical_key": physical_key,
        })

    with (REPO_ROOT / "caldwell-catalog.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("ra_h") or not row.get("dec_deg"):
                continue
            objects.append({
                "label": row["caldwell"],
                "ra_deg": float(row["ra_h"]) * 15.0,
                "dec_deg": float(row["dec_deg"]),
                "physical_key": row.get("catalog") or row["caldwell"],
            })

    # Finest NGC is a curated observing list, not a substitute name for NGC.
    # Keep its membership visible even when the same physical object is also
    # Messier or Caldwell.
    with (REPO_ROOT / "finest-ngc-catalog.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("ra_h") or not row.get("dec_deg"):
                continue
            objects.append({
                "label": f"Finest {row['finest_ngc']}",
                "ra_deg": float(row["ra_h"]) * 15.0,
                "dec_deg": float(row["dec_deg"]),
                "physical_key": row.get("catalog") or f"Finest {row['finest_ngc']}",
            })
    return objects


def normalized_catalog_identity(value):
    """Normalize simple NGC/IC identities without collapsing composite regions."""
    text = re.sub(r"\\s+", " ", str(value or "").strip().upper())
    match = re.fullmatch(r"(NGC|IC)\\s*(\\d+)", text)
    return f"{match.group(1)} {match.group(2)}" if match else text


def visible_deep_sky_objects(center, xmin, xmax, ymin, ymax):
    """Project curated catalog objects and combine duplicate physical targets."""
    grouped = {}
    for obj in deep_sky_catalog_objects():
        point = project(obj["ra_deg"], obj["dec_deg"], *center)
        if point is None or not (xmin <= point[0] <= xmax and ymin <= point[1] <= ymax):
            continue
        key = normalized_catalog_identity(obj["physical_key"])
        item = grouped.setdefault(key, {"point": point, "labels": []})
        if obj["label"] not in item["labels"]:
            item["labels"].append(obj["label"])
    return list(grouped.values())


def fixed_object_database_record(fixed_id):
    path = REPO_ROOT / "database" / "fixed-objects.json"
    if not path.exists():
        raise RuntimeError(f"Fixed-object database is missing at {path.relative_to(REPO_ROOT)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for obj in payload.get("fixed_objects") or []:
        if obj.get("fixed_object_id") == fixed_id:
            return obj
    raise RuntimeError(f"Target fixed_object_id {fixed_id} is absent from fixed-object database")


def fixed_object_metadata(fixed_id, fallback=None):
    meta = dict(fallback or {})
    record = fixed_object_database_record(fixed_id)
    for source_record in record.get("source_records") or []:
        facts = source_record.get("facts") or {}
        if facts.get("name") and not meta.get("proper_name"):
            meta["proper_name"] = facts["name"]
        if facts.get("constellation") and not meta.get("constellation_abbreviation"):
            meta["constellation_abbreviation"] = facts["constellation"]
        ra_h = facts.get("ra_h")
        dec_deg = facts.get("dec_deg")
        if meta.get("ra_deg") is None and ra_h not in (None, ""):
            try:
                meta["ra_deg"] = float(ra_h) * 15.0
            except (TypeError, ValueError):
                pass
        if meta.get("dec_deg") is None and dec_deg not in (None, ""):
            try:
                meta["dec_deg"] = float(dec_deg)
            except (TypeError, ValueError):
                pass
    return meta


def bayer_label(identity, star=None):
    stored = str(identity.get("bayer") or "").strip()
    if stored:
        return greek_bayer_symbol(stored)
    if star is None:
        return ""
    return greek_bayer_symbol(star.bayer)


def chart_bayer_label(identity, star, figure_abbreviation):
    full = bayer_label(identity, star)
    if not full:
        return ""
    parts = full.split()
    greek = parts[0]
    constellation = str(identity.get("constellation_abbreviation") or star.con or "").strip()
    if constellation and figure_abbreviation and constellation != figure_abbreviation:
        return f"{greek} {constellation}"
    return greek


def legend_label(identity, star=None):
    full = bayer_label(identity, star)
    if not full:
        return ""
    greek = full.split()[0]
    proper = str(identity.get("proper_name") or (star.proper if star else "") or "").strip()
    return f"{greek} — {proper}" if proper else greek


def greek_sort_key(identity, star=None):
    full = bayer_label(identity, star)
    if not full:
        return (999, 999, "")
    bayer = full.split()[0]
    symbol = bayer[0]
    suffix_match = re.search(r"(\d+)$", bayer)
    suffix = int(suffix_match.group(1)) if suffix_match else 0
    return (GREEK_ORDER.get(symbol, 999), suffix, bayer)


def draw_path(ax, path, idx, center, color, linewidth):
    points = [project(idx[ref].ra_deg, idx[ref].dec_deg, *center) for ref in path]
    points = [point for point in points if point is not None]
    if len(points) >= 2:
        ax.plot([point[0] for point in points], [point[1] for point in points],
                color=color, linewidth=linewidth, alpha=0.95, zorder=2)


def render(spec: dict, stars, output: Path) -> None:
    idx = complete_index(stars)
    identities_by_ref, identities_by_id = identity_index(spec)
    figure_paths = spec.get("figure_paths") or []
    guide_constellations = spec.get("guide_constellations") or []
    guide_paths = [path for guide in guide_constellations for path in (guide.get("paths") or [])]
    asterisms = spec.get("asterisms") or []
    target_identity = spec.get("target_identity") or spec.get("artwork_owner_identity") or {}
    target_id = target_identity.get("fixed_object_id")
    if target_id is None:
        raise RuntimeError("Finder target must resolve through hidden fixed_object_id")
    target_star_identity = identities_by_id.get(target_id)
    target_ref = target_identity.get("renderer_ref") or (target_star_identity or {}).get("renderer_ref")
    if target_ref and target_ref not in idx:
        raise RuntimeError(f"Target renderer_ref {target_ref} is not present in coordinate catalog")
    refs = refs_from_paths(figure_paths) | refs_from_paths(guide_paths)
    if target_ref:
        refs.add(target_ref)
    asterisms = list(asterisms)
    labeled_asterism_names = {str(item.get("name") or "") for item in asterisms if item.get("name")}
    for asterism in asterisms:
        refs |= refs_from_paths(asterism.get("paths") or [])
    missing_identities = sorted(ref for ref in refs if ref not in identities_by_ref)
    if missing_identities:
        raise RuntimeError("Configured stars have no database identity: " + ", ".join(missing_identities))
    missing = sorted(ref for ref in refs if ref not in idx)
    if missing:
        raise RuntimeError("Configured stars not found in coordinate catalog: " + ", ".join(missing))
    target_meta = fixed_object_metadata(target_id, target_identity)
    if target_ref:
        target_star = idx[target_ref]
        target_ra = target_star.ra_deg
        target_dec = target_star.dec_deg
        target_meta.setdefault("proper_name", target_star.proper)
        target_meta.setdefault("constellation_abbreviation", target_star.con)
    else:
        target_star = None
        if target_meta.get("ra_deg") is None or target_meta.get("dec_deg") is None:
            raise RuntimeError(f"Target fixed_object_id {target_id} has no authoritative sky coordinates")
        target_ra = target_meta["ra_deg"]
        target_dec = target_meta["dec_deg"]
    planet_position = spec.get("planet_position") or {}
    planet_name = str((spec.get("finder_relation") or {}).get("planet") or "").strip()
    planet_ra = planet_position.get("ra_deg")
    planet_dec = planet_position.get("dec_deg")
    has_planet = planet_name and planet_ra is not None and planet_dec is not None
    # Frame planet finders around the useful navigation path rather than the
    # entire parent constellation.  The full figure remains available to draw,
    # but an unrelated distant arm of that figure must not force a needlessly
    # wide field.  A named asterism is the preferred recognition context.
    framing_paths = spec.get("framing_paths", figure_paths + guide_paths)
    if has_planet:
        # A moving-body finder is framed by the navigation route, never by the
        # full extent of a constellation.  If a genuinely local asterism was
        # selected upstream, include it.  Otherwise frame only the planet and
        # its local hop star; the constellation figure may be clipped naturally
        # at the edges instead of inflating the chart into a catalog plot.
        framing_paths = guide_paths
        if asterisms:
            framing_paths += [
                path for asterism in asterisms for path in (asterism.get("paths") or [])
            ]
    framing_refs = refs_from_paths(framing_paths)
    if target_ref:
        framing_refs.add(target_ref)
    center_stars = [idx[ref] for ref in framing_refs]
    if target_star is not None:
        center_stars.append(target_star)
    else:
        center_stars.append(SimpleNamespace(ra_deg=target_ra, dec_deg=target_dec))
    if has_planet:
        center_stars.append(SimpleNamespace(ra_deg=float(planet_ra), dec_deg=float(planet_dec)))
    center = spherical_center(center_stars)
    projected_geometry = [
        project(idx[ref].ra_deg, idx[ref].dec_deg, *center)
        for ref in framing_refs
    ]
    target_point = project(target_ra, target_dec, *center)
    planet_point = project(float(planet_ra), float(planet_dec), *center) if has_planet else None
    if target_point is not None:
        projected_geometry.append(target_point)
    if planet_point is not None:
        projected_geometry.append(planet_point)
    projected_geometry = [point for point in projected_geometry if point is not None]
    if not projected_geometry:
        raise RuntimeError("Accepted geometry produced no visible projected points")
    xs = [point[0] for point in projected_geometry]
    ys = [point[1] for point in projected_geometry]
    compact_guide = "framing_paths" in spec and not has_planet
    span = max(max(xs) - min(xs), max(ys) - min(ys), 2.0 if compact_guide else 8.0)
    pad = max(0.5 if compact_guide else 2.5, span * 0.18)
    if has_planet and not asterisms:
        # Give the local constellation context and edge labels a little more room.
        pad = max(3.5, span * 0.24)
    xmin, xmax = min(xs) - pad, max(xs) + pad
    ymin, ymax = min(ys) - pad, max(ys) + pad
    # Ambient figures and asterisms enter only after framing. They supply
    # clipped context for every finder, including moving bodies, without
    # changing the navigation route, projection center, padding or bounds.
    drawn_names = {spec.get("name"), *(guide.get("name") for guide in guide_constellations)}
    ambient_figures = [
        item for item in visible_context(spec.get("candidate_constellations") or [], idx, center,
                                        xmin, xmax, ymin, ymax)
        if item.get("name") not in drawn_names
    ]
    ambient_paths = [path for item in ambient_figures for path in item["paths"]]
    asterism_keys = {item.get("id") or item.get("name") for item in asterisms}
    for item in visible_context(spec.get("candidate_asterisms") or [], idx, center,
                                xmin, xmax, ymin, ymax):
        key = item.get("id") or item.get("name")
        if key not in asterism_keys:
            asterisms.append(item)
            asterism_keys.add(key)
            labeled_asterism_names.add(str(item.get("name") or ""))
    visible = []
    for star in stars:
        if star.mag > 7:
            continue
        point = project(star.ra_deg, star.dec_deg, *center)
        if point and xmin <= point[0] <= xmax and ymin <= point[1] <= ymax:
            visible.append((point[0], point[1], star))
    fig, ax = plt.subplots(figsize=(8.2, 8.2), facecolor=NIGHT)
    ax.set_facecolor(NIGHT)
    ax.set_xlim(xmax, xmin)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    if visible:
        ax.scatter([item[0] for item in visible], [item[1] for item in visible],
                   s=[marker_area(item[2].mag, 7) for item in visible], color=STAR,
                   linewidths=0, zorder=3)
    for path in figure_paths:
        draw_path(ax, path, idx, center, FIGURE_BLUE, 2.7)
    for path in guide_paths:
        draw_path(ax, path, idx, center, FIGURE_BLUE, 2.2)
    for path in ambient_paths:
        draw_path(ax, path, idx, center, FIGURE_BLUE, 2.2)

    # Deep-sky catalog objects are selected geometrically from the actual
    # displayed field.  Messier/Caldwell aliases for one physical object share
    # a marker and label; no constellation- or week-specific exceptions.
    deep_sky = visible_deep_sky_objects(center, xmin, xmax, ymin, ymax)
    if deep_sky:
        ax.scatter(
            [item["point"][0] for item in deep_sky],
            [item["point"][1] for item in deep_sky],
            s=42, facecolors="none", edgecolors=TEXT, linewidths=1.1, zorder=4,
        )
    boundaries = load_iau_boundaries()
    planet_constellation, planet_abbreviation = (
        constellation_for_position(float(planet_ra), float(planet_dec), boundaries)
        if has_planet else ("", "")
    )
    projected_boundaries = []
    for boundary_name, boundary_abbreviation, boundary in boundaries:
        boundary_points = projected_path(boundary, center)
        if len(boundary_points) >= 2:
            projected_boundaries.append((boundary_name, boundary_abbreviation, boundary_points))
    boundary_segments = []
    for _, _, boundary_points in projected_boundaries:
        boundary_segments.extend(zip(boundary_points, boundary_points[1:]))
    figure_refs = []
    seen = set()
    for path in figure_paths:
        for ref in path:
            if ref not in seen:
                seen.add(ref)
                figure_refs.append(ref)
    figure_constellation = spec.get("name") or ""
    figure_abbreviation = str(target_meta.get("constellation_abbreviation") or "").strip()
    # Reserve every visible deep-sky circle before placing any text.  A label
    # must clear its own marker and neighboring catalog objects alike.
    fig.canvas.draw()
    occupied_labels = [marker_obstacle_bbox(ax, item["point"], 42, 1.1)
                       for item in deep_sky]
    figure_points = []
    figure_segments = []
    for path in figure_paths + guide_paths + ambient_paths:
        path_points = [project(idx[ref].ra_deg, idx[ref].dec_deg, *center) for ref in path]
        path_points = [point for point in path_points if point is not None]
        figure_segments.extend(zip(path_points, path_points[1:]))
    for ref in figure_refs:
        star = idx[ref]
        point = project(star.ra_deg, star.dec_deg, *center)
        if point is not None:
            figure_points.append(point)
    asterism_segments = []
    for asterism in asterisms:
        for path in asterism.get("paths") or []:
            path_points = [project(idx[ref].ra_deg, idx[ref].dec_deg, *center) for ref in path if ref in idx]
            path_points = [point for point in path_points if point is not None]
            asterism_segments.extend(zip(path_points, path_points[1:]))

    guide_refs = []
    seen_guides = set()
    for path in guide_paths:
        for ref in path:
            if ref not in seen_guides:
                seen_guides.add(ref)
                guide_refs.append(ref)
    labeled_star_ids = set()
    for ref in figure_refs + guide_refs:
        star = idx[ref]
        identity = identities_by_ref[ref]
        fixed_id = identity["fixed_object_id"]
        if fixed_id in labeled_star_ids:
            continue
        point = project(star.ra_deg, star.dec_deg, *center)
        if point is None or (compact_guide and not (xmin <= point[0] <= xmax and ymin <= point[1] <= ymax)):
            continue
        if identity.get("fixed_object_id") == target_id:
            continue
        label = chart_bayer_label(identity, star, figure_abbreviation)
        if label:
            place_label(ax, label, point, occupied_labels, obstacle_segments=figure_segments + asterism_segments,
                        require_clear=compact_guide)
            labeled_star_ids.add(fixed_id)
    for item in deep_sky:
        place_label(
            ax, " / ".join(item["labels"]), item["point"], occupied_labels,
            color=TEXT, fontsize=8, zorder=6,
            obstacle_segments=figure_segments + asterism_segments,
            require_clear=True,
        )
    if figure_constellation and figure_points:
        figure_region = visible_figure_region(
            figure_paths, idx, center, xmin, xmax, ymin, ymax,
        )
        label_points = figure_region[:-1] if figure_region else [
            p for p in figure_points if xmin <= p[0] <= xmax and ymin <= p[1] <= ymax
        ]
        if label_points:
            constellation_point = (sum(x for x, _ in label_points) / len(label_points),
                                   sum(y for _, y in label_points) / len(label_points))
            place_constellation_label(
                ax, figure_constellation, constellation_point, occupied_labels,
                obstacle_segments=figure_segments + asterism_segments + boundary_segments,
                boundary_points=figure_region,
            )
    for guide in guide_constellations + ambient_figures:
        guide_name = str(guide.get("name") or guide.get("abbreviation") or "").strip()
        points = []
        for path in guide.get("paths") or []:
            for ref in path:
                if ref in idx:
                    point = project(idx[ref].ra_deg, idx[ref].dec_deg, *center)
                    if point is not None:
                        points.append(point)
        if guide_name and points:
            guide_region = visible_figure_region(
                guide.get("paths") or [], idx, center, xmin, xmax, ymin, ymax,
            )
            label_points = guide_region[:-1] if guide_region else [
                p for p in points if xmin <= p[0] <= xmax and ymin <= p[1] <= ymax
            ]
            if label_points:
                guide_point = (sum(x for x, _ in label_points) / len(label_points),
                               sum(y for _, y in label_points) / len(label_points))
                place_constellation_label(
                    ax, guide_name, guide_point, occupied_labels,
                    obstacle_segments=figure_segments + asterism_segments + boundary_segments,
                    boundary_points=guide_region,
                )
    home_abbreviation = str(spec.get("constellation_abbreviation") or figure_abbreviation).strip()
    neighbor_points = {}
    for boundary_name, boundary_abbreviation, boundary_points in projected_boundaries:
        points = boundary_points
        if len(points) < 2 or not path_hits_view(points, xmin, xmax, ymin, ymax):
            continue
        ax.plot([p[0] for p in points], [p[1] for p in points],
                color=BOUNDARY_WHITE, linewidth=0.8, alpha=0.8,
                linestyle="--", zorder=3)
        visible_points = [p for p in points if xmin <= p[0] <= xmax and ymin <= p[1] <= ymax]
        if visible_points and boundary_abbreviation not in (home_abbreviation, planet_abbreviation):
            neighbor_points.setdefault(boundary_abbreviation, (boundary_name, points))
    for neighbor_abbreviation, (neighbor_name, points) in neighbor_points.items():
        visible_points = [p for p in points if xmin <= p[0] <= xmax and ymin <= p[1] <= ymax]
        if not visible_points:
            continue
        point = (sum(x for x, _ in visible_points) / len(visible_points),
                 sum(y for _, y in visible_points) / len(visible_points))
        place_boundary_label(
            ax, CONSTELLATION_DISPLAY_NAMES.get(neighbor_name, neighbor_name), neighbor_abbreviation, point, occupied_labels,
            points, obstacle_segments=boundary_segments,
            color=BOUNDARY_WHITE, fontsize=10, zorder=5,
        )
    drawn_abbreviations = {str(item.get("abbreviation") or "")
                           for item in guide_constellations + ambient_figures}
    if has_planet and planet_abbreviation != home_abbreviation and planet_abbreviation not in drawn_abbreviations:
        planet_boundary = next(
            points for _, abbreviation, points in projected_boundaries
            if abbreviation == planet_abbreviation and MplPath(points).contains_point(planet_point)
        )
        # Reserve the whole planetary marker, not just its central point.
        px, py = ax.transData.transform(planet_point)
        marker_radius = (math.sqrt(115) / 2 + 1.6 / 2 + 3) * fig.dpi / 72
        occupied_labels.append(Bbox.from_extents(
            px - marker_radius, py - marker_radius,
            px + marker_radius, py + marker_radius,
        ))
        place_constellation_label(
            ax, planet_constellation, planet_point, occupied_labels,
            obstacle_segments=figure_segments + asterism_segments + boundary_segments
            + [(planet_point, planet_point)],
            boundary_points=planet_boundary,
        )
    labeled_asterism_refs = set()
    for asterism in asterisms:
        asterism_points = []
        for path in asterism.get("paths") or []:
            draw_path(ax, path, idx, center, ASTERISM_GREEN, 3.2)
            for ref in path:
                if ref in idx:
                    point = project(idx[ref].ra_deg, idx[ref].dec_deg, *center)
                    if point is not None and xmin <= point[0] <= xmax and ymin <= point[1] <= ymax:
                        asterism_points.append(point)
                        # Asterisms are recognition landmarks, so their named
                        # member stars must remain recognizable too.  This is a
                        # general rule (for example Kaus Australis in the
                        # Teapot), never a star-specific exception.
                        identity = identities_by_ref.get(ref) or {}
                        proper = str(identity.get("proper_name") or idx[ref].proper or "").strip()
                        if proper and ref not in labeled_asterism_refs and identity.get("fixed_object_id") != target_id:
                            place_label(
                                ax, proper, point, occupied_labels,
                                color=ASTERISM_GREEN, fontsize=9, zorder=7,
                                obstacle_segments=figure_segments + asterism_segments + boundary_segments,
                                require_clear=compact_guide,
                            )
                            labeled_asterism_refs.add(ref)
        name = str(asterism.get("name") or "")
        if name in labeled_asterism_names and asterism_points:
            label_point = (
                sum(point[0] for point in asterism_points) / len(asterism_points),
                sum(point[1] for point in asterism_points) / len(asterism_points),
            )
            place_label(
                ax, name, label_point, occupied_labels,
                color=ASTERISM_GREEN, fontsize=9, zorder=7,
                obstacle_segments=figure_segments + asterism_segments + boundary_segments,
                require_clear=compact_guide,
            )
    if target_point is None:
        raise RuntimeError(f"Target fixed_object_id {target_id} is outside the projection")
    ax.scatter([target_point[0]], [target_point[1]], s=210, facecolors="none",
               edgecolors=TARGET_YELLOW, linewidths=2.6, zorder=8)
    target_name = str(target_meta.get("proper_name") or target_identity.get("name") or "").strip()
    target_greek = ""
    if target_star_identity and target_star is not None:
        full = bayer_label(target_star_identity, target_star)
        target_greek = full.split()[0] if full else ""
    target_const = str(target_meta.get("constellation_abbreviation") or "").strip()
    target_bayer = " ".join(part for part in (target_greek, target_const) if part) if target_greek else ""
    target_chart_label = ", ".join(part for part in (target_bayer, target_name) if part)
    # Split long guide-star names so their labels can sit next to the ring
    # without moving across the field to find room for one wide line.
    if has_planet and target_bayer and len(target_name) >= 12:
        target_chart_label = f"{target_bayer}\n{target_name}"
    if not target_chart_label:
        target_chart_label = str(target_identity.get("name") or "Target")
    place_target_label(
        ax, target_chart_label, target_point, occupied_labels,
        obstacle_segments=figure_segments + asterism_segments + boundary_segments,
        marker_radius_points=math.sqrt(210) / 2 + 2.6 / 2,
    )
    if has_planet:
        if planet_point is None:
            raise RuntimeError(f"Planet {planet_name} is outside the finder projection")
        ax.scatter([planet_point[0]], [planet_point[1]], s=115, marker="o",
                   facecolors=TARGET_YELLOW, edgecolors=TARGET_YELLOW, linewidths=1.6, zorder=10)
        place_target_label(
            ax, planet_name, planet_point, occupied_labels,
            obstacle_segments=figure_segments + asterism_segments + boundary_segments,
            marker_radius_points=math.sqrt(115) / 2 + 1.6 / 2,
        )
        # Add every other preserved weekly planet that genuinely lies in this
        # Pathfinder's displayed field. These are context objects, not finder
        # targets, so use smaller open markers and ordinary text.
        for body in spec.get("solar_system_field") or []:
            body_name = str(body.get("name") or "").strip()
            if not body_name or body_name == planet_name:
                continue
            ra, dec = body.get("ra_deg"), body.get("dec_deg")
            if ra is None or dec is None:
                continue
            point = project(float(ra), float(dec), *center)
            if point is None or not (xmin <= point[0] <= xmax and ymin <= point[1] <= ymax):
                continue
            ax.scatter([point[0]], [point[1]], s=58, marker="o",
                       facecolors="none", edgecolors=TEXT, linewidths=1.2, zorder=8)
            place_label(
                ax, body_name, point, occupied_labels, color=TEXT, fontsize=9, zorder=8,
                obstacle_segments=figure_segments + asterism_segments + boundary_segments,
                require_clear=True,
            )
    if has_planet:
        # A moving-body finder is named for the route the reader actually uses:
        # body + useful landmark + full constellation.
        reference_name = str((spec.get("finder_relation") or {}).get("reference_star") or target_name).strip()
        title = planet_finder_title(
            planet_name, planet_constellation, reference_name, figure_constellation,
        )
    elif target_star is not None and target_bayer and target_name and figure_constellation:
        title = f"{target_bayer}, {target_name} in {figure_constellation}"
    else:
        title = f"{target_name} in {figure_constellation}" if target_name and figure_constellation else (target_name or figure_constellation)
    if not title:
        title = spec.get("chart_title") or "Stellar Finder"
    ax.set_title(title, color=TEXT, fontsize=14, pad=12)
    kilroy = datetime.now(timezone.utc).strftime("Kilroy: Artwork · %Y-%m-%d %H:%M:%S UTC")
    ax.text(0.995, 1.015, kilroy, transform=ax.transAxes, ha="right", va="bottom", fontsize=6, color=TEXT)
    ax.text(0.5, -0.035, "East ←                                      → West",
            transform=ax.transAxes, ha="center", va="top", fontsize=8, color=TEXT)
    legend_entries = []
    for ref in figure_refs:
        identity = identities_by_ref[ref]
        star = idx[ref]
        point = project(star.ra_deg, star.dec_deg, *center)
        if compact_guide and (point is None or not (xmin <= point[0] <= xmax and ymin <= point[1] <= ymax)):
            continue
        if bayer_label(identity, star):
            legend_entries.append((identity, star))
    legend_entries.sort(key=lambda pair: greek_sort_key(pair[0], pair[1]))
    legend = [legend_label(identity, star) for identity, star in legend_entries]
    legend = [item for item in legend if item]
    if legend:
        # SVG text does not automatically wrap long Matplotlib legend strings.
        # Keep complete entries together and bound the saved SVG's canvas.
        legend_lines, current = [], ""
        for entry in legend:
            candidate = f"{current}   ·   {entry}" if current else entry
            if current and len(candidate) > 70:
                legend_lines.append(current)
                current = entry
            else:
                current = candidate
        if current:
            legend_lines.append(current)
        legend_text = "\n".join(legend_lines)
        # Finder legends belong only in the bottom legend area.  A prior
        # renderer emitted the same legend at the top and bottom, which made
        # descriptor artwork appear to have a duplicated legend.
        ax.text(0.5, -0.075, legend_text, transform=ax.transAxes,
                ha="center", va="top", fontsize=7, color=TEXT, wrap=True)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.08, 1, 0.96))
    fig.savefig(output, format="svg", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("hyg_catalog", type=Path)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    render(spec, load_hyg(args.hyg_catalog), args.output)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
