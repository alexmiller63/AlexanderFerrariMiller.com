#!/usr/bin/env python3
"""Render Sky Notes stellar finders from accepted renderer specs.

This renderer is deliberately separate from the legacy reference-finder renderer.
It obeys the Sky Notes visual contract: blue constellation figures, green
asterisms, yellow open target circles, and no target arrows. Geometry is
consumed exactly as supplied by the generated spec; it is never inferred.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import matplotlib.pyplot as plt
from matplotlib.path import Path as MplPath

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


def projected_path(points, center):
    return [p for p in (project(ra, dec, *center) for ra, dec in points) if p is not None]


def path_hits_view(points, xmin, xmax, ymin, ymax):
    return any(xmin <= x <= xmax and ymin <= y <= ymax for x, y in points)


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


def place_target_label(ax, label, point, occupied_labels, obstacle_segments=()):
    """Place the target label in a genuinely clear area, including full-width moves."""
    style = dict(
        ha="left", va="center", fontsize=10, color=TARGET_YELLOW,
        bbox=dict(facecolor=NIGHT, edgecolor="none", pad=0.8), zorder=9,
    )
    probe = ax.annotate(label, point, xytext=(14, 0), textcoords="offset points", **style)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    probe_bbox = probe.get_window_extent(renderer=renderer)
    width = probe_bbox.width
    height = probe_bbox.height
    probe.remove()

    # Include the familiar right-of-target position first, then explicitly try
    # one complete rendered label width to the left before expanding outward.
    offsets = [
        (14, 0), (-width - 14, 0),
        (14, height), (-width - 14, height),
        (14, -height), (-width - 14, -height),
    ]
    for radius in range(2, 7):
        dx = radius * max(width * 0.5, 18)
        dy = radius * max(height, 12)
        offsets.extend(((dx, 0), (-width - dx, 0),
                        (dx, dy), (-width - dx, dy),
                        (dx, -dy), (-width - dx, -dy)))

    best = None
    for rank, (dx, dy) in enumerate(offsets):
        annotation = ax.annotate(label, point, xytext=(dx, dy), textcoords="offset points", **style)
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

    _, _, dx, dy = best
    annotation = ax.annotate(label, point, xytext=(dx, dy), textcoords="offset points", **style)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    occupied_labels.append(annotation.get_window_extent(renderer=renderer).expanded(1.08, 1.16))
    return annotation


def place_constellation_label(ax, label, point, occupied_labels, obstacle_segments=()):
    """Place a constellation name by searching outward until a genuinely clear area is found."""
    probe = ax.annotate(label, point, xytext=(0, 0), textcoords="offset points",
                        fontsize=16, color=FIGURE_BLUE, zorder=5)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    width = probe.get_window_extent(renderer=renderer).width
    height = probe.get_window_extent(renderer=renderer).height
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
    asterisms = spec.get("asterisms") or []
    target_identity = spec.get("target_identity") or spec.get("artwork_owner_identity") or {}
    target_id = target_identity.get("fixed_object_id")
    if target_id is None:
        raise RuntimeError("Finder target must resolve through hidden fixed_object_id")
    target_star_identity = identities_by_id.get(target_id)
    target_ref = target_identity.get("renderer_ref") or (target_star_identity or {}).get("renderer_ref")
    if target_ref and target_ref not in idx:
        raise RuntimeError(f"Target renderer_ref {target_ref} is not present in coordinate catalog")
    refs = refs_from_paths(figure_paths)
    if target_ref:
        refs.add(target_ref)
    asterisms = list(asterisms)
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
    center_stars = [idx[ref] for ref in refs_from_paths(figure_paths)]
    if target_star is not None:
        center_stars.append(target_star)
    else:
        center_stars.append(SimpleNamespace(ra_deg=target_ra, dec_deg=target_dec))
    center = spherical_center(center_stars)
    projected_geometry = [project(idx[ref].ra_deg, idx[ref].dec_deg, *center) for ref in refs]
    target_point = project(target_ra, target_dec, *center)
    if target_point is not None:
        projected_geometry.append(target_point)
    projected_geometry = [point for point in projected_geometry if point is not None]
    if not projected_geometry:
        raise RuntimeError("Accepted geometry produced no visible projected points")
    xs = [point[0] for point in projected_geometry]
    ys = [point[1] for point in projected_geometry]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 8.0)
    pad = max(2.5, span * 0.18)
    xmin, xmax = min(xs) - pad, max(xs) + pad
    ymin, ymax = min(ys) - pad, max(ys) + pad
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
                   s=[marker_area(item[2].mag, 7) for item in visible], color=STAR, zorder=1)
    for path in figure_paths:
        draw_path(ax, path, idx, center, FIGURE_BLUE, 2.7)
    # Project all IAU boundaries before label placement so constellation names
    # avoid the complete rendered geometry, not just figure/asterism lines.
    projected_boundaries = []
    for boundary_name, boundary_abbreviation, boundary in load_iau_boundaries():
        boundary_points = projected_path(boundary, center)
        if len(boundary_points) >= 2:
            projected_boundaries.append(
                (boundary_name, boundary_abbreviation, boundary_points)
            )
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
    asterism_segments = []
    for asterism in asterisms:
        for path in asterism.get("paths") or []:
            path_points = [project(idx[ref].ra_deg, idx[ref].dec_deg, *center) for ref in path if ref in idx]
            path_points = [point for point in path_points if point is not None]
            asterism_segments.extend(zip(path_points, path_points[1:]))
    occupied_labels = []
    figure_points = []
    figure_segments = []
    for path in figure_paths:
        path_points = [project(idx[ref].ra_deg, idx[ref].dec_deg, *center) for ref in path]
        path_points = [point for point in path_points if point is not None]
        figure_segments.extend(zip(path_points, path_points[1:]))
    for ref in figure_refs:
        star = idx[ref]
        identity = identities_by_ref[ref]
        point = project(star.ra_deg, star.dec_deg, *center)
        if point is None:
            continue
        figure_points.append(point)
    for candidate in spec.get("candidate_asterisms") or []:
        visible_paths = []
        for path in candidate.get("paths") or []:
            if any(ref not in idx for ref in path):
                continue
            points = [project(idx[ref].ra_deg, idx[ref].dec_deg, *center) for ref in path]
            points = [point for point in points if point is not None]
            if path_hits_view(points, xmin, xmax, ymin, ymax):
                visible_paths.append(path)
        if visible_paths:
            asterisms.append(dict(candidate, paths=visible_paths))
    # Candidate asterisms are part of the rendered geometry, so they must be
    # known before any star/constellation label is accepted. Otherwise a label
    # can be placed in a location that is later occupied by a candidate path.
    asterism_segments = []
    for asterism in asterisms:
        for path in asterism.get("paths") or []:
            path_points = [project(idx[ref].ra_deg, idx[ref].dec_deg, *center) for ref in path if ref in idx]
            path_points = [point for point in path_points if point is not None]
            asterism_segments.extend(zip(path_points, path_points[1:]))

    for ref in figure_refs:
        star = idx[ref]
        identity = identities_by_ref[ref]
        point = project(star.ra_deg, star.dec_deg, *center)
        if point is None:
            continue
        if identity.get("fixed_object_id") == target_id:
            continue
        label = chart_bayer_label(identity, star, figure_abbreviation)
        if label:
            place_label(ax, label, point, occupied_labels, obstacle_segments=figure_segments + asterism_segments)
    if figure_constellation and figure_points:
        constellation_point = (sum(x for x, _ in figure_points) / len(figure_points),
                               sum(y for _, y in figure_points) / len(figure_points))
        place_constellation_label(
            ax, figure_constellation, constellation_point, occupied_labels,
            obstacle_segments=figure_segments + asterism_segments + boundary_segments,
        )
    home_abbreviation = str(spec.get("constellation_abbreviation") or "").strip()
    neighbor_points = {}
    for boundary_name, boundary_abbreviation, boundary_points in projected_boundaries:
        points = boundary_points
        if len(points) < 2 or not path_hits_view(points, xmin, xmax, ymin, ymax):
            continue
        ax.plot([p[0] for p in points], [p[1] for p in points],
                color=BOUNDARY_WHITE, linewidth=0.8, alpha=0.8,
                linestyle="--", zorder=3)
        visible_points = [p for p in points if xmin <= p[0] <= xmax and ymin <= p[1] <= ymax]
        if visible_points and boundary_abbreviation != home_abbreviation:
            neighbor_points.setdefault(boundary_abbreviation, (boundary_name, points))
    for neighbor_abbreviation, (neighbor_name, points) in neighbor_points.items():
        visible_points = [p for p in points if xmin <= p[0] <= xmax and ymin <= p[1] <= ymax]
        if not visible_points:
            continue
        point = (sum(x for x, _ in visible_points) / len(visible_points),
                 sum(y for _, y in visible_points) / len(visible_points))
        place_boundary_label(
            ax, CONSTELLATION_DISPLAY_NAMES.get(neighbor_name, neighbor_name), neighbor_abbreviation, point, occupied_labels,
            points,
            obstacle_segments=boundary_segments,
            color=BOUNDARY_WHITE, fontsize=10, zorder=5,
        )
    for asterism in asterisms:
        for path in asterism.get("paths") or []:
            draw_path(ax, path, idx, center, ASTERISM_GREEN, 3.2)
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
    target_bayer = " ".join(part for part in (target_greek, target_const) if part)
    target_chart_label = ", ".join(part for part in (target_bayer, target_name) if part)
    if not target_chart_label:
        target_chart_label = str(target_identity.get("name") or "Target")
    place_target_label(
        ax, target_chart_label, target_point, occupied_labels,
        obstacle_segments=figure_segments + asterism_segments + boundary_segments,
    )
    # Stellar titles use the same Greek Bayer symbol as the chart label.
    if target_star is not None and target_bayer and target_name and figure_constellation:
        title = f"{target_bayer}, {target_name} in {figure_constellation}"
    else:
        title = f"{target_name} in {figure_constellation}" if target_name and figure_constellation else (target_name or figure_constellation)
    if not title:
        title = spec.get("chart_title") or "Stellar Finder"
    ax.set_title(title, color=TEXT, fontsize=14, pad=12)
    ax.text(0.5, -0.035, "East ←                                      → West",
            transform=ax.transAxes, ha="center", va="top", fontsize=8, color=TEXT)
    legend_entries = []
    for ref in figure_refs:
        identity = identities_by_ref[ref]
        star = idx[ref]
        if bayer_label(identity, star):
            legend_entries.append((identity, star))
    legend_entries.sort(key=lambda pair: greek_sort_key(pair[0], pair[1]))
    legend = [legend_label(identity, star) for identity, star in legend_entries]
    legend = [item for item in legend if item]
    if legend:
        legend_text = "   ·   ".join(legend)
        ax.text(0.5, 1.035, legend_text, transform=ax.transAxes,
                ha="center", va="bottom", fontsize=7, color=TEXT, wrap=True)
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