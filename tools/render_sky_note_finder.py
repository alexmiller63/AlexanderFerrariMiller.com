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
from matplotlib.patches import Polygon
from matplotlib.collections import LineCollection
from matplotlib.transforms import Bbox

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from render_stellar_finders import greek_bayer_symbol, load_hyg, marker_area, project, spherical_center, star_index
from tools.constellation_names import constellation_names
from tools.notation_modes import refresh_document, SVG_MODE_SCRIPT

NIGHT = "#071423"
STAR = "#f7f7f2"
TEXT = "#f3f5f7"
FIGURE_BLUE = "#5c8fe8"
ASTERISM_GREEN = "#59c86d"
TARGET_YELLOW = "#ffd84d"
BOUNDARY_WHITE = "#ffffff"
BODY_SYMBOLS = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", "Mars": "♂",
    "Jupiter": "♃", "Saturn": "♄", "Ceres": "⚳", "Uranus": "♅",
    "Neptune": "♆", "Pluto": "♇",
}
ZODIAC_SIGNS = (
    ("♈", "Aries"), ("♉", "Taurus"), ("♊", "Gemini"), ("♋", "Cancer"),
    ("♌", "Leo"), ("♍", "Virgo"), ("♎", "Libra"), ("♏", "Scorpio"),
    ("♐", "Sagittarius"), ("♑", "Capricorn"), ("♒", "Aquarius"), ("♓", "Pisces"),
)
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


def ecliptic_coordinates():
    """J2000 mean ecliptic in the coordinate catalog's equatorial frame."""
    obliquity = math.radians(23.439291111)
    for degree in range(721):
        longitude = math.radians(degree / 2)
        yield (math.degrees(math.atan2(math.cos(obliquity) * math.sin(longitude),
                                      math.cos(longitude))) % 360,
               math.degrees(math.asin(math.sin(obliquity) * math.sin(longitude))))


def visible_ecliptic_signs(center, xmin, xmax, ymin, ymax):
    """Label full 30-degree sectors only when their exact midpoints are visible."""
    points = [project(ra, dec, *center) for ra, dec in ecliptic_coordinates()]
    result = []
    for index, (symbol, name) in enumerate(ZODIAC_SIGNS):
        # Half-degree samples put each sector's center at 15° + 30° * index.
        # Clipping a sector must never relocate its label toward a boundary.
        point = points[index * 60 + 30]
        if point is not None and xmin <= point[0] <= xmax and ymin <= point[1] <= ymax:
            result.append((symbol, name, point))
    return result


def ecliptic_sign_boundary_segments(center, xmin, xmax, ymin, ymax):
    """Short perpendicular ticks at exact 30-degree ecliptic longitudes."""
    points = [project(ra, dec, *center) for ra, dec in ecliptic_coordinates()]
    half_length = min(xmax - xmin, ymax - ymin) * 0.009
    result = []
    for longitude in range(0, 360, 30):
        index = longitude * 2
        point = points[index]
        before, after = points[(index - 1) % 720], points[(index + 1) % 720]
        if point is None or before is None or after is None:
            continue
        if not (xmin <= point[0] <= xmax and ymin <= point[1] <= ymax):
            continue
        dx, dy = after[0] - before[0], after[1] - before[1]
        length = math.hypot(dx, dy)
        if not length:
            continue
        size = half_length * (1.5 if longitude == 0 else 1.0)
        nx, ny = -dy / length * size, dx / length * size
        segment = clip_view_segment(
            (point[0] - nx, point[1] - ny), (point[0] + nx, point[1] + ny),
            xmin, xmax, ymin, ymax,
        )
        if segment is not None:
            result.append((longitude, segment))
    return result


def include_nearby_ecliptic(center, planet_point, xmin, xmax, ymin, ymax):
    """Include useful nearby ecliptic context with at most 25% linear growth."""
    original = (xmin, xmax, ymin, ymax)
    if planet_point is None:
        return original
    # No growth is needed when the ecliptic already crosses the frame.
    if sky_reference_segments(center, *original)[1][3]:
        return original
    points = projected_path(ecliptic_coordinates(), center)
    if not points:
        return original
    base_span = max(xmax - xmin, ymax - ymin)
    margin = base_span * 0.04
    # Prefer the smallest extension that reveals the ecliptic in this field;
    # use proximity to the body to break ties, rather than pulling in a distant
    # point along the same great circle.
    def framing_cost(point):
        width = max(xmax, point[0] + margin) - min(xmin, point[0] - margin)
        height = max(ymax, point[1] + margin) - min(ymin, point[1] - margin)
        return (max(width, height), math.hypot(point[0] - planet_point[0],
                                             point[1] - planet_point[1]))
    nearest = min(points, key=framing_cost)
    left, right = min(xmin, nearest[0] - margin), max(xmax, nearest[0] + margin)
    bottom, top = min(ymin, nearest[1] - margin), max(ymax, nearest[1] + margin)
    span = max(right - left, top - bottom)
    if span > base_span * 1.25:
        return original
    xmid, ymid = (left + right) / 2, (bottom + top) / 2
    return (xmid - span / 2, xmid + span / 2,
            ymid - span / 2, ymid + span / 2)


def sky_reference_segments(center, xmin, xmax, ymin, ymax):
    """Clip J2000 equator/ecliptic to the existing finder frame."""
    result = []
    for name, color, style in (("Celestial equator", "#71cbd1", "--"),
                               ("Ecliptic", "#e6a36b", "-.")):
        points = []
        coordinates = (ecliptic_coordinates() if name == "Ecliptic"
                       else ((degree / 2, 0.0) for degree in range(721)))
        for ra, dec in coordinates:
            points.append(project(ra, dec, *center))
        segments = []
        for start, end in zip(points, points[1:]):
            if start is not None and end is not None:
                segment = clip_view_segment(start, end, xmin, xmax, ymin, ymax)
                if segment is not None:
                    segments.append(segment)
        result.append((name, color, style, segments))
    return result


def coordinate_grid_segments(center, xmin, xmax, ymin, ymax):
    """Sample J2000 hour meridians and ten-degree declination parallels."""
    result = []
    curves = [(f"{hour}h", "ra", [(hour * 15.0, step / 2) for step in range(-180, 181)])
              for hour in range(24)]
    # The poles are points. Dec 0 also carries the prominent equator overlay.
    curves += [(f"{dec:+d}°" if dec else "0°", "dec", [(step / 2, float(dec)) for step in range(721)])
               for dec in range(-80, 81, 10)]
    for label, kind, coordinates in curves:
        points = [project(ra, dec, *center) for ra, dec in coordinates]
        segments = []
        for start, end in zip(points, points[1:]):
            if start is not None and end is not None:
                clipped = clip_view_segment(start, end, xmin, xmax, ymin, ymax)
                if clipped is not None:
                    segments.append(clipped)
        if segments:
            result.append((label, kind, segments))
    return result


def label_coordinate_grid(ax, grid, occupied_labels):
    """Label actual frame crossings, keeping text inside the chart edges."""
    xmin, xmax = sorted(ax.get_xlim())
    ymin, ymax = sorted(ax.get_ylim())
    tolerance = max(xmax - xmin, ymax - ymin) * 1e-6
    for label, kind, segments in grid:
        endpoints = [point for segment in segments for point in segment]
        crossings = []
        for point in endpoints:
            x, y = point
            sides = [(abs(y - ymax), "top"), (abs(y - ymin), "bottom"),
                     (abs(x - xmax), "left"), (abs(x - xmin), "right")]
            distance, side = min(sides)
            if distance <= tolerance:
                preferred = side in ({"top", "bottom"} if kind == "ra" else {"left", "right"})
                crossings.append((not preferred, point, side))
        for _, point, side in sorted(crossings):
            dx, dy, ha, va = {
                "top": (0, -4, "center", "top"),
                "bottom": (0, 4, "center", "bottom"),
                "left": (4, 0, "left", "center"),
                "right": (-4, 0, "right", "center"),
            }[side]
            annotation = ax.annotate(label, point, xytext=(dx, dy), textcoords="offset points",
                                     ha=ha, va=va, fontsize=7, color="#9aa9b8", zorder=5)
            bbox = annotation.get_window_extent(ax.figure.canvas.get_renderer()).expanded(1.1, 1.1)
            if (not ax.bbox.contains(bbox.x0, bbox.y0)
                    or not ax.bbox.contains(bbox.x1, bbox.y1)
                    or any(bbox.overlaps(other) for other in occupied_labels)):
                annotation.remove()
                continue
            occupied_labels.append(bbox)
            break


def make_svg_responsive(output):
    """Retain the SVG viewBox while filling a standalone browser's width."""
    text = output.read_text(encoding="utf-8")
    def resize(match):
        root = match.group(0)
        root = re.sub(r' width="[^"]*"', ' width="100%"', root)
        root = re.sub(r' height="[^"]*"', '', root)
        return root[:-1] + ' style="display:block;width:100%;height:auto" preserveAspectRatio="xMidYMid meet">'
    text = re.sub(r'<svg\b[^>]*>', resize, text, count=1)
    output.write_text(text, encoding="utf-8")


def add_constellation_notation(output):
    """Keep all naming modes in one standalone SVG with no extra render pass."""
    import xml.etree.ElementTree as ET
    ns = "http://www.w3.org/2000/svg"
    ET.register_namespace("", ns)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    tree = ET.parse(output)
    root = tree.getroot()
    root.set("data-notation-mode", "1")
    style = ET.SubElement(root, f"{{{ns}}}style")
    style.text = '''
    [id^="constellation-"][id$="-latin"],
    [id^="constellation-"][id$="-mixed"],
    [id^="star-label-"][id$="-latin"],
    [id^="star-label-"][id$="-mixed"] { display:none }
    svg[data-notation-mode="2"] [id^="constellation-"][id$="-greek"],
    svg[data-notation-mode="3"] [id^="constellation-"][id$="-greek"],
    svg[data-notation-mode="2"] [id^="star-label-"][id$="-greek"],
    svg[data-notation-mode="3"] [id^="star-label-"][id$="-greek"] { display:none }
    svg[data-notation-mode="2"] [id^="constellation-"][id$="-latin"],
    svg[data-notation-mode="3"] [id^="constellation-"][id$="-mixed"],
    svg[data-notation-mode="2"] [id^="star-label-"][id$="-latin"],
    svg[data-notation-mode="3"] [id^="star-label-"][id$="-mixed"] { display:inline }
    [data-notation-choice] { cursor:pointer; fill:#f3f5f7 }
    [data-notation-choice][aria-pressed="true"] { fill:#ffd84d; text-decoration:underline }
    '''
    # Body names switch with the stars, including their displaced leaders.
    style.text += '''
    [id^="body-label-"][id$="-latin"], [id^="body-label-"][id$="-mixed"] { display:none }
    svg[data-notation-mode="2"] [id^="body-label-"][id$="-greek"],
    svg[data-notation-mode="3"] [id^="body-label-"][id$="-greek"] { display:none }
    svg[data-notation-mode="2"] [id^="body-label-"][id$="-latin"],
    svg[data-notation-mode="3"] [id^="body-label-"][id$="-mixed"] { display:inline }
    '''
    style.text += style.text[style.text.index('    [id^="body-label-"]'):].replace(
        'body-label-', 'ecliptic-label-',
    )
    x, y, width, height = map(float, root.get("viewBox").split())
    root.set("viewBox", f"{x} {y} {width} {height + 30}")
    ET.SubElement(root, f"{{{ns}}}rect", {
        "x": str(x), "y": str(y + height), "width": str(width),
        "height": "30", "fill": NIGHT,
    })
    for fraction, mode, label in ((.2, "1", "Greek / Symbols"),
                                   (.5, "2", "English"), (.8, "3", "Mixed")):
        button = ET.SubElement(root, f"{{{ns}}}text", {
            "x": str(x + width * fraction), "y": str(y + height + 19),
            "text-anchor": "middle", "font-size": "11", "font-family": "sans-serif",
            "role": "button", "tabindex": "0", "data-notation-choice": mode,
            "aria-pressed": "true" if mode == "1" else "false",
        })
        button.text = label
    script = ET.SubElement(root, f"{{{ns}}}script", {"type": "application/ecmascript"})
    script.text = SVG_MODE_SCRIPT
    tree.write(output, encoding="utf-8", xml_declaration=True)
    # Matplotlib leaves indentation-only lines in newly generated groups.
    document = refresh_document(output.read_text(encoding="utf-8"))
    output.write_text("\n".join(line.rstrip() for line in document.splitlines()), encoding="utf-8")


def place_named_constellation(ax, name, abbreviation, point, occupied_labels,
                              obstacle_segments=(), boundary_points=None, neighbor=False):
    """Reserve the widest name so switching mode cannot introduce collisions."""
    identity, names = constellation_names(name, abbreviation)
    fontsize = 10 if neighbor else 16
    measurements = {}
    for label in set(names.values()):
        probe = ax.annotate(label, point, fontsize=fontsize, annotation_clip=False)
        measurements[label] = probe.get_window_extent(ax.figure.canvas.get_renderer()).width
        probe.remove()
    widest = max(measurements, key=measurements.get)
    if neighbor:
        annotation = place_boundary_label(
            ax, widest, widest, point, occupied_labels, boundary_points,
            obstacle_segments=obstacle_segments,
        )
    else:
        annotation = place_constellation_label(
            ax, widest, point, occupied_labels, obstacle_segments=obstacle_segments,
            boundary_points=boundary_points,
        )
    if annotation is None:
        return None
    for mode, label in names.items():
        text = ax.annotate(
            label, point, xytext=annotation.get_position(), textcoords="offset points",
            fontsize=fontsize, color=annotation.get_color(), zorder=annotation.get_zorder(),
            annotation_clip=False,
        )
        text.set_gid(f"constellation-name-{identity}-{mode}")
    annotation.remove()
    return identity


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
    # Label searches reuse thousands of segments at fixed axes geometry.
    # Cache their exact transformed endpoints, invalidating on any affine
    # change. Nonlinear axes keep the direct transformation path.
    if ax.get_xscale() == ax.get_yscale() == "linear":
        signature = ax.transData.get_affine().to_values()
        state = getattr(ax, "_finder_segment_display_cache", None)
        if state is None or state[0] != signature:
            state = (signature, {})
            ax._finder_segment_display_cache = state
        key = (tuple(start), tuple(end))
        endpoints = state[1].get(key)
        if endpoints is None:
            endpoints = (ax.transData.transform(start), ax.transData.transform(end))
            state[1][key] = endpoints
    else:
        endpoints = (ax.transData.transform(start), ax.transData.transform(end))
    (x1, y1), (x2, y2) = endpoints
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
        # Axes are fixed before placement; measure the candidate without
        # repainting all three notation variants for every search position.
        renderer = ax.figure.canvas.get_renderer()
        bbox = annotation.get_window_extent(renderer=renderer).expanded(1.08, 1.16)
        label_hits = sum(bbox.overlaps(other) for other in occupied_labels)
        geometry_hits = sum(segment_hits_display_bbox(ax, start, end, bbox)
                            for start, end in obstacle_segments)
        score = label_hits + geometry_hits
        if require_clear and not (ax.bbox.contains(bbox.x0, bbox.y0)
                                  and ax.bbox.contains(bbox.x1, bbox.y1)):
            score += 1
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
            renderer = ax.figure.canvas.get_renderer()
            bbox = annotation.get_window_extent(renderer=renderer).expanded(1.08, 1.16)
            annotation.update_bbox_position_size(renderer)
            label_hits = sum(bbox.overlaps(other) for other in occupied_labels)
            geometry_hits = sum(segment_hits_display_bbox(ax, start, end, bbox)
                                for start, end in obstacle_segments)
            marker_bbox = annotation.get_bbox_patch().get_window_extent(renderer=renderer)
            marker_x = min(max(anchor_x, marker_bbox.x0), marker_bbox.x1)
            marker_y = min(max(anchor_y, marker_bbox.y0), marker_bbox.y1)
            marker_distance = math.hypot(marker_x - anchor_x, marker_y - anchor_y)
            marker_hits = marker_distance < marker_clearance_points * ax.figure.dpi / 72
            score = label_hits + geometry_hits + marker_hits
            if not (ax.bbox.contains(bbox.x0, bbox.y0) and ax.bbox.contains(bbox.x1, bbox.y1)):
                score += 1
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
    renderer = ax.figure.canvas.get_renderer()
    occupied_labels.append(annotation.get_window_extent(renderer=renderer).expanded(1.08, 1.16))
    annotation.update_bbox_position_size(renderer)
    # A displaced label needs a visible connection to its protected marker.
    text_bbox = annotation.get_bbox_patch().get_window_extent(renderer=renderer)
    endpoint = (min(max(anchor_x, text_bbox.x0), text_bbox.x1),
                min(max(anchor_y, text_bbox.y0), text_bbox.y1))
    distance_points = math.hypot(endpoint[0] - anchor_x, endpoint[1] - anchor_y) * points_per_pixel
    if distance_points > marker_radius_points + 10:
        ax.annotate("", point, xytext=ax.transData.inverted().transform(endpoint),
                    arrowprops=dict(arrowstyle="-", color=TARGET_YELLOW, linewidth=0.8,
                                    shrinkA=3, shrinkB=marker_radius_points + 2), zorder=8)
    return annotation


def place_constellation_label(ax, label, point, occupied_labels, obstacle_segments=(),
                              boundary_points=None):
    """Place a constellation name by searching outward until a genuinely clear area is found."""
    probe = ax.annotate(label, point, xytext=(0, 0), textcoords="offset points",
                        fontsize=16, color=FIGURE_BLUE, zorder=5, annotation_clip=False)
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

    if boundary_points is not None:
        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
        anchor_display = ax.transData.transform(point)
        for iy in range(1, 10):
            for ix in range(1, 10):
                candidate = (xmin + (xmax - xmin) * ix / 10,
                             ymin + (ymax - ymin) * iy / 10)
                if MplPath(boundary_points).contains_point(candidate):
                    display = ax.transData.transform(candidate)
                    offsets.append(tuple((display - anchor_display) * 72 / ax.figure.dpi))

    for dx, dy in offsets:
        annotation = ax.annotate(label, point, xytext=(dx, dy), textcoords="offset points",
                                 fontsize=16, color=FIGURE_BLUE, zorder=5, annotation_clip=False)
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
                                     fontsize=16, color=FIGURE_BLUE, zorder=5, annotation_clip=False)
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


def star_notation_labels(identity, star, figure_abbreviation, target=False):
    symbol = chart_bayer_label(identity, star, figure_abbreviation)
    proper = str(identity.get("proper_name") or star.proper or "").strip()
    greek_names = ("Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Iota Kappa Lambda Mu Nu "
                   "Xi Omicron Pi Rho Sigma Tau Upsilon Phi Chi Psi Omega").split()
    latin = proper or " ".join(dict(zip(GREEK_SYMBOL_ORDER, greek_names)).get(c, c)
                               for c in symbol.split())
    mixed = f"{symbol} — {latin}" if symbol and latin else (symbol or latin)
    if target and symbol and len(latin) >= 12:
        mixed = f"{symbol}\n{latin}"
    constellation = str(identity.get("constellation_abbreviation") or star.con or "").strip()
    if constellation == "Psc" and bayer_label(identity, star).split()[0:1] == ["β"]:
        separator = "\n" if target else " — "
        mixed = "Beta Piscium" + (separator + proper if proper else "")
    return {"greek": symbol or latin, "latin": latin, "mixed": mixed}


def place_ecliptic_notation(ax, symbol, name, point, occupied_labels, **kwargs):
    return place_star_notation(
        ax, {}, {"greek": symbol, "latin": f"Sign of {name}",
                 "mixed": f"{symbol} Sign of {name}"},
        point, occupied_labels, label_id=f"ecliptic-label-{name.lower()}",
        color="#e6a36b", fontsize=10, **kwargs,
    )


def place_body_notation(ax, name, point, occupied_labels, **kwargs):
    symbol = BODY_SYMBOLS[name]
    return place_star_notation(
        ax, {}, {"greek": symbol, "latin": name, "mixed": f"{symbol} {name}"},
        point, occupied_labels, label_id=f"body-label-{name.lower()}", **kwargs,
    )


def place_star_notation(ax, identity, labels, point, occupied_labels,
                        obstacle_segments=(), target=False, color=TEXT, fontsize=9,
                        label_id=None, marker_radius_points=None):
    """Place each mode near its star and reserve all variants for later labels."""
    label_id = label_id or f"star-label-{identity['fixed_object_id']}"
    prior = list(occupied_labels)
    reservations = []
    placed = {}
    for mode, label in labels.items():
        occupied_labels[:] = prior
        before = len(ax.texts)
        if target:
            annotation = place_target_label(
                ax, label, point, occupied_labels, obstacle_segments=obstacle_segments,
                marker_radius_points=(math.sqrt(210) / 2 + 2.6 / 2
                                      if marker_radius_points is None else marker_radius_points),
            )
        else:
            annotation = place_label(
                ax, label, point, occupied_labels, color=color, fontsize=fontsize,
                obstacle_segments=obstacle_segments, require_clear=True,
            )
        if annotation is not None:
            annotation.set_gid(f"{label_id}-{mode}")
            for artist in list(ax.texts)[before:]:
                if artist is not annotation:
                    artist.set_gid(f"{label_id}-leader-{mode}")
                    if artist.arrow_patch is not None:
                        artist.arrow_patch.set_gid(f"{label_id}-leader-path-{mode}")
            reservations.extend(occupied_labels[len(prior):])
            placed[mode] = annotation
    occupied_labels[:] = prior + reservations
    return placed


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


def lunar_disk_geometry(ra_deg, dec_deg, center, snapshot):
    """Project the true angular disk and its sun-facing illuminated surface."""
    radius = math.radians(float(snapshot["angular_diameter_deg"]) / 2)
    phase = math.radians(float(snapshot["phase_angle_deg"]))
    pa = math.radians(float(snapshot["bright_limb_position_angle_deg"]))
    ra0, dec0 = math.radians(ra_deg), math.radians(dec_deg)

    def surface_point(u, v):
        east = u * math.sin(pa) + v * math.cos(pa)
        north = u * math.cos(pa) - v * math.sin(pa)
        separation = radius * math.hypot(east, north)
        bearing = math.atan2(east, north)
        dec = math.asin(math.sin(dec0) * math.cos(separation)
                        + math.cos(dec0) * math.sin(separation) * math.cos(bearing))
        ra = ra0 + math.atan2(math.sin(bearing) * math.sin(separation) * math.cos(dec0),
                             math.cos(separation) - math.sin(dec0) * math.sin(dec))
        return project(math.degrees(ra), math.degrees(dec), *center)

    outline = [surface_point(math.cos(i * math.tau / 180), math.sin(i * math.tau / 180))
               for i in range(180)]
    limb, terminator = [], []
    for i in range(181):
        v = -math.cos(i * math.pi / 180)
        u = math.sin(i * math.pi / 180)
        limb.append(surface_point(u, v))
        terminator.append(surface_point(-math.cos(phase) * u, v))
    return outline, limb + list(reversed(terminator))


def draw_lunar_disk(ax, ra_deg, dec_deg, center, snapshot):
    outline, lit_surface = lunar_disk_geometry(ra_deg, dec_deg, center, snapshot)
    ax.add_patch(Polygon(outline, closed=True, facecolor="#303844", edgecolor=TEXT,
                         linewidth=0.6, zorder=10))
    ax.add_patch(Polygon(lit_surface, closed=True, facecolor=STAR, edgecolor="none", zorder=11))
    display = ax.transData.transform(outline)
    clearance = 4 * ax.figure.dpi / 72
    return Bbox.from_extents(display[:, 0].min() - clearance, display[:, 1].min() - clearance,
                            display[:, 0].max() + clearance, display[:, 1].max() + clearance)


def draw_moon_closeup(ax, snapshot, segments):
    """Insert a clearly enlarged phase view in the least obstructed chart space."""
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    obstacles = [text.get_window_extent(renderer).expanded(1.08, 1.15)
                 for text in ax.texts if text.get_visible()]
    obstacles += [patch.get_window_extent(renderer).expanded(1.15, 1.15)
                  for patch in ax.patches]
    candidates = []
    for y in (0.64, 0.49, 0.34, 0.19, 0.04):
        for x in (0.65, 0.50, 0.35, 0.20, 0.05):
            box = Bbox.from_bounds(x, y, 0.30, 0.32).transformed(ax.transAxes)
            hits = sum(box.overlaps(other) for other in obstacles)
            hits += sum(segment_hits_display_bbox(ax, start, end, box)
                        for start, end in segments)
            candidates.append((hits, x, y))
    _, x, y = min(candidates, key=lambda candidate: candidate[0])
    inset = ax.inset_axes([x, y, 0.30, 0.32], zorder=20)
    inset.set_facecolor(ax.get_facecolor())
    radius = float(snapshot["angular_diameter_deg"]) / 2
    inset.set_xlim(radius * 1.5, -radius * 1.5)
    inset.set_ylim(-radius * 1.5, radius * 1.5)
    inset.set_aspect("equal")
    draw_lunar_disk(inset, 0, 0, (0, 0), snapshot)
    inset.text(0.5, 0.97, "Moon · enlarged", transform=inset.transAxes,
               ha="center", va="top", color=TEXT, fontsize=8)
    illumination = float(snapshot["illuminated_fraction"]) * 100
    inset.text(0.5, 0.03, f"{illumination:.0f}% illuminated\nMonday 00:00 UTC",
               transform=inset.transAxes, ha="center", va="bottom",
               color=TEXT, fontsize=7)
    inset.set_xticks([])
    inset.set_yticks([])
    for spine in inset.spines.values():
        spine.set_edgecolor(TEXT)
        spine.set_linewidth(1.2)


def draw_finder_overview(ax, spec, stars, idx, target_ra, target_dec, target_name):
    """Show the supplied guide and target pattern without widening the close-up."""
    overview = spec["overview"]
    guide = overview["guide_identity"]
    guide_star = idx[guide["renderer_ref"]]
    patterns = list(overview.get("asterisms") or []) + list(spec.get("asterisms") or [])
    paths = [path for pattern in patterns for path in pattern.get("paths") or []]
    refs = refs_from_paths(paths) | {guide["renderer_ref"]}
    center = spherical_center([idx[ref] for ref in refs])
    points = [project(idx[ref].ra_deg, idx[ref].dec_deg, *center) for ref in refs]
    points = [point for point in points if point is not None]
    xs, ys = zip(*points)
    pad = max(1.0, max(max(xs) - min(xs), max(ys) - min(ys)) * 0.12)
    xmin, xmax, ymin, ymax = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    ax.set_facecolor(NIGHT)
    ax.set_xlim(xmax, xmin)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    field = []
    for star in stars:
        point = project(star.ra_deg, star.dec_deg, *center)
        if star.mag <= 6 and point is not None and xmin <= point[0] <= xmax and ymin <= point[1] <= ymax:
            field.append((point, star))
    if field:
        ax.scatter([point[0] for point, _ in field], [point[1] for point, _ in field],
                   s=[marker_area(star.mag, 6) for _, star in field], color=STAR, linewidths=0, zorder=3)
    # Context is selected only after the route establishes this panel's bounds.
    for record in visible_context(spec.get("candidate_constellations") or [], idx, center,
                                  xmin, xmax, ymin, ymax):
        for path in record["paths"]:
            draw_path(ax, path, idx, center, FIGURE_BLUE, 1.4)
    selected = {pattern.get("id") for pattern in patterns}
    for record in visible_context(spec.get("candidate_asterisms") or [], idx, center,
                                  xmin, xmax, ymin, ymax):
        if record.get("id") not in selected:
            for path in record["paths"]:
                draw_path(ax, path, idx, center, ASTERISM_GREEN, 1.2)
    segments = []
    for path in paths:
        draw_path(ax, path, idx, center, ASTERISM_GREEN, 2.0)
        projected = [project(idx[ref].ra_deg, idx[ref].dec_deg, *center) for ref in path]
        segments.extend((a, b) for a, b in zip(projected, projected[1:]) if a is not None and b is not None)
    occupied = []
    guide_point = project(guide_star.ra_deg, guide_star.dec_deg, *center)
    place_target_label(ax, guide.get("proper_name") or guide_star.proper, guide_point, occupied,
                       obstacle_segments=segments,
                       marker_radius_points=math.sqrt(marker_area(guide_star.mag, 6)) / 2)
    target_point = project(target_ra, target_dec, *center)
    place_target_label(ax, target_name, target_point, occupied, obstacle_segments=segments)
    for pattern in overview.get("asterisms") or []:
        pattern_points = [project(idx[ref].ra_deg, idx[ref].dec_deg, *center)
                          for ref in refs_from_paths(pattern["paths"])]
        pattern_points = [point for point in pattern_points if point is not None]
        point = tuple(sum(p[i] for p in pattern_points) / len(pattern_points) for i in (0, 1))
        place_label(ax, pattern["name"], point, occupied, color=ASTERISM_GREEN,
                    obstacle_segments=segments, require_clear=True)
    ax.set_title(f"{guide.get('proper_name') or guide_star.proper} to {target_name} — overview",
                 color=TEXT, fontsize=12, pad=10)
    ax.text(0.02, 0.02, "North up · East ←   → West", transform=ax.transAxes,
            ha="left", va="bottom", color=TEXT, fontsize=8)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


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
    if not has_planet and "framing_paths" not in spec and not spec.get("overview"):
        # An entire constellation can span most of the sky.  For an object
        # finder, select a local hop around the target instead of allowing
        # distant figure vertices to dictate the field of view.  The complete
        # figure is still drawn below, clipped to these local bounds.
        def angular_distance(ref):
            star = idx[ref]
            ra1, dec1 = math.radians(target_ra), math.radians(target_dec)
            ra2, dec2 = math.radians(star.ra_deg), math.radians(star.dec_deg)
            cosine = (math.sin(dec1) * math.sin(dec2)
                      + math.cos(dec1) * math.cos(dec2) * math.cos(ra1 - ra2))
            return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))

        nearby = sorted(framing_refs, key=lambda ref: (angular_distance(ref), ref))
        # Two landmarks give a useful locating route without expanding to
        # the farthest corners of a sprawling constellation.
        framing_refs = set(nearby[:2])
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
    pattern_target = compact_guide and any(
        str(item.get("name") or "").strip().casefold()
        == str(target_meta.get("proper_name") or target_identity.get("name") or "").strip().casefold()
        for item in asterisms
    )
    span = max(max(xs) - min(xs), max(ys) - min(ys), 2.0 if compact_guide else 8.0)
    pad = max(0.5 if compact_guide else 2.5, span * 0.18)
    if has_planet and not asterisms:
        # Give the local constellation context and edge labels a little more room.
        pad = max(3.5, span * 0.24)
    xmin, xmax = min(xs) - pad, max(xs) + pad
    ymin, ymax = min(ys) - pad, max(ys) + pad
    # Keep equal angular scale without squeezing a north/south route into a
    # narrow strip. Expand only the shorter field dimension around its center.
    if not spec.get("overview"):
        field_span = max(xmax - xmin, ymax - ymin)
        xmid, ymid = (xmin + xmax) / 2, (ymin + ymax) / 2
        xmin, xmax = xmid - field_span / 2, xmid + field_span / 2
        ymin, ymax = ymid - field_span / 2, ymid + field_span / 2
        if has_planet:
            xmin, xmax, ymin, ymax = include_nearby_ecliptic(
                center, planet_point, xmin, xmax, ymin, ymax,
            )
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
    asterism_keys = {item["id"] for item in asterisms}
    for item in visible_context(spec.get("candidate_asterisms") or [], idx, center,
                                xmin, xmax, ymin, ymax):
        key = item["id"]
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
    # Keep these axes positions through saving: resizing after label checks
    # would invalidate the reserved text and marker boxes.
    if spec.get("overview"):
        fig, overview_ax = plt.subplots(figsize=(8.2, 8.2), facecolor=NIGHT)
        draw_finder_overview(overview_ax, spec, stars, idx, target_ra, target_dec,
                             str(target_meta.get("proper_name") or target_identity.get("name") or ""))
        ax = overview_ax.inset_axes([0.54, 0.18, 0.43, 0.43], zorder=20)
    else:
        fig, ax = plt.subplots(figsize=(8.2, 8.2), facecolor=NIGHT)
    ax.set_facecolor(NIGHT)
    ax.set_xlim(xmax, xmin)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    reference_lines = sky_reference_segments(center, xmin, xmax, ymin, ymax)
    coordinate_grid = coordinate_grid_segments(center, xmin, xmax, ymin, ymax)
    ax.add_collection(LineCollection(
        [segment for _, _, segments in coordinate_grid for segment in segments],
        colors="#71849a", linewidths=0.5, linestyles=":", alpha=0.35, zorder=0.5,
    ))
    for name, color, style, segments in reference_lines:
        for start, end in segments:
            ax.plot([start[0], end[0]], [start[1], end[1]], color=color,
                    linestyle=style, linewidth=0.9, alpha=0.8, zorder=1)
    sign_boundaries = ecliptic_sign_boundary_segments(center, xmin, xmax, ymin, ymax)
    for longitude, (start, end) in sign_boundaries:
        tick, = ax.plot([start[0], end[0]], [start[1], end[1]],
                       color="#e6a36b", linewidth=1.8 if longitude == 0 else 1.1,
                       zorder=2)
        tick.set_gid(f"ecliptic-sign-boundary-{longitude}")
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
    if pattern_target:
        # The pattern is the target, rather than a point at its catalog center.
        # Suppress its catalog alias marker as well as the yellow target ring.
        target_catalog_labels = {
            record.get("source_key")
            for record in fixed_object_database_record(target_id).get("source_records") or []
        }
        deep_sky = [item for item in deep_sky
                    if not target_catalog_labels.intersection(item["labels"])]
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
    planet_constellation = CONSTELLATION_DISPLAY_NAMES.get(planet_constellation, planet_constellation)
    projected_boundaries = []
    for boundary_name, boundary_abbreviation, boundary in boundaries:
        boundary_points = projected_path(boundary, center)
        if len(boundary_points) >= 2:
            projected_boundaries.append((boundary_name, boundary_abbreviation, boundary_points))
    boundary_segments = [segment for _, segment in sign_boundaries]
    boundary_segments.extend(segment for _, _, _, segments in reference_lines for segment in segments)
    for _, _, boundary_points in projected_boundaries:
        boundary_segments.extend(zip(boundary_points, boundary_points[1:]))
    figure_refs = []
    seen = set()
    for path in figure_paths:
        for ref in path:
            if ref not in seen:
                seen.add(ref)
                figure_refs.append(ref)
    figure_constellation = CONSTELLATION_DISPLAY_NAMES.get(spec.get("name"), spec.get("name") or "")
    figure_abbreviation = str(target_meta.get("constellation_abbreviation") or "").strip()
    # Reserve every visible deep-sky circle before placing any text.  A label
    # must clear its own marker and neighboring catalog objects alike.
    fig.canvas.draw()
    occupied_labels = [marker_obstacle_bbox(ax, item["point"], 42, 1.1)
                       for item in deep_sky]
    if has_planet:
        for body in [dict(planet_position, name=planet_name)] + list(spec.get("solar_system_field") or []):
            if body.get("ra_deg") is None or body.get("dec_deg") is None:
                continue
            body_point = project(float(body["ra_deg"]), float(body["dec_deg"]), *center)
            if body_point and xmin <= body_point[0] <= xmax and ymin <= body_point[1] <= ymax:
                is_target = body.get("name") == planet_name
                occupied_labels.append(marker_obstacle_bbox(
                    ax, body_point, 115 if is_target else 58, 1.6 if is_target else 1.2,
                ))
    if target_point is not None and not pattern_target:
        occupied_labels.append(marker_obstacle_bbox(ax, target_point, 210, 2.6))
    moon_bbox = None
    moon_snapshot = spec.get("moon_disk")
    if has_planet and moon_snapshot:
        moon_position = (planet_position if planet_name == "Moon" else next(
            (body for body in spec.get("solar_system_field") or [] if body.get("name") == "Moon"), None,
        ))
        if moon_position:
            moon_point = project(float(moon_position["ra_deg"]), float(moon_position["dec_deg"]), *center)
            if moon_point and xmin <= moon_point[0] <= xmax and ymin <= moon_point[1] <= ymax:
                moon_bbox = draw_lunar_disk(ax, float(moon_position["ra_deg"]),
                                           float(moon_position["dec_deg"]), center, moon_snapshot)
                occupied_labels.append(moon_bbox)
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

    if target_point is None:
        raise RuntimeError(f"Target fixed_object_id {target_id} is outside the projection")
    if not pattern_target:
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
    if target_star_identity and target_star is not None:
        place_star_notation(
            ax, target_star_identity,
            star_notation_labels(target_star_identity, target_star, figure_abbreviation, target=True),
            target_point, occupied_labels,
            obstacle_segments=figure_segments + asterism_segments + boundary_segments,
            target=True,
        )
    else:
        place_target_label(
            ax, target_chart_label, target_point, occupied_labels,
            obstacle_segments=figure_segments + asterism_segments + boundary_segments,
            marker_radius_points=0 if pattern_target else math.sqrt(210) / 2 + 2.6 / 2,
        )

    guide_refs = []
    seen_guides = set()
    for path in guide_paths:
        for ref in path:
            if ref not in seen_guides:
                seen_guides.add(ref)
                guide_refs.append(ref)
    labeled_constellations = set()
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
            annotation = place_named_constellation(
                ax, figure_constellation, figure_abbreviation, constellation_point, occupied_labels,
                obstacle_segments=figure_segments + asterism_segments + boundary_segments,
                boundary_points=figure_region,
            )
            if annotation is not None:
                labeled_constellations.add(annotation)
    for guide in guide_constellations + ambient_figures:
        guide_abbreviation = str(guide.get("abbreviation") or "").strip()
        if guide_abbreviation in labeled_constellations:
            continue
        guide_name = str(guide.get("name") or guide_abbreviation).strip()
        guide_name = CONSTELLATION_DISPLAY_NAMES.get(guide_name, guide_name)
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
                annotation = place_named_constellation(
                    ax, guide_name, guide_abbreviation, guide_point, occupied_labels,
                    obstacle_segments=figure_segments + asterism_segments + boundary_segments,
                    boundary_points=guide_region,
                )
                if annotation is not None:
                    labeled_constellations.add(annotation)
    neighbor_points = {}
    for boundary_name, boundary_abbreviation, boundary_points in projected_boundaries:
        points = boundary_points
        if len(points) < 2 or not path_hits_view(points, xmin, xmax, ymin, ymax):
            continue
        ax.plot([p[0] for p in points], [p[1] for p in points],
                color=BOUNDARY_WHITE, linewidth=0.8, alpha=0.8,
                linestyle="--", zorder=3)
        visible_points = [p for p in points if xmin <= p[0] <= xmax and ymin <= p[1] <= ymax]
        if visible_points and boundary_abbreviation not in labeled_constellations and boundary_abbreviation != planet_abbreviation:
            neighbor_points.setdefault(boundary_abbreviation, (boundary_name, points))
    for neighbor_abbreviation, (neighbor_name, points) in neighbor_points.items():
        visible_points = [p for p in points if xmin <= p[0] <= xmax and ymin <= p[1] <= ymax]
        if not visible_points:
            continue
        point = (sum(x for x, _ in visible_points) / len(visible_points),
                 sum(y for _, y in visible_points) / len(visible_points))
        place_named_constellation(
            ax, neighbor_name, neighbor_abbreviation, point, occupied_labels,
            boundary_points=points, obstacle_segments=boundary_segments, neighbor=True,
        )
    if has_planet and planet_abbreviation not in labeled_constellations:
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
        place_named_constellation(
            ax, planet_constellation, planet_abbreviation, planet_point, occupied_labels,
            obstacle_segments=figure_segments + asterism_segments + boundary_segments
            + [(planet_point, planet_point)],
            boundary_points=planet_boundary,
        )
    for asterism in asterisms:
        asterism_points = []
        for path in asterism.get("paths") or []:
            draw_path(ax, path, idx, center, ASTERISM_GREEN, 3.2)
            for ref in path:
                if ref in idx:
                    point = project(idx[ref].ra_deg, idx[ref].dec_deg, *center)
                    if point is not None and xmin <= point[0] <= xmax and ymin <= point[1] <= ymax:
                        asterism_points.append(point)
        name = str(asterism.get("name") or "")
        target_pattern_name = str(target_meta.get("proper_name") or target_identity.get("name") or "").strip()
        if (name in labeled_asterism_names and asterism_points
                and name.casefold() != target_pattern_name.casefold()):
            label_point = (
                sum(point[0] for point in asterism_points) / len(asterism_points),
                sum(point[1] for point in asterism_points) / len(asterism_points),
            )
            place_label(
                ax, name, label_point, occupied_labels,
                color=ASTERISM_GREEN, fontsize=9, zorder=7,
                obstacle_segments=figure_segments + asterism_segments + boundary_segments,
                require_clear=True,
            )
    labeled_star_ids = set()
    asterism_refs = refs_from_paths([path for item in asterisms for path in item.get("paths") or []])
    for ref in dict.fromkeys(figure_refs + guide_refs + sorted(asterism_refs)):
        star = idx[ref]
        identity = identities_by_ref.get(ref)
        if identity is None:
            continue
        fixed_id = identity["fixed_object_id"]
        if fixed_id in labeled_star_ids:
            continue
        point = project(star.ra_deg, star.dec_deg, *center)
        if point is None or not (xmin <= point[0] <= xmax and ymin <= point[1] <= ymax):
            continue
        if identity.get("fixed_object_id") == target_id:
            continue
        labels = star_notation_labels(identity, star, figure_abbreviation)
        if labels["greek"]:
            place_star_notation(
                ax, identity, labels, point, occupied_labels,
                color=ASTERISM_GREEN if ref in asterism_refs else TEXT,
                obstacle_segments=figure_segments + asterism_segments + boundary_segments,
            )
            labeled_star_ids.add(fixed_id)
    for item in deep_sky:
        place_label(
            ax, " / ".join(item["labels"]), item["point"], occupied_labels,
            color=TEXT, fontsize=8, zorder=6,
            obstacle_segments=figure_segments + asterism_segments,
            require_clear=True,
        )
    if has_planet:
        if planet_point is None:
            raise RuntimeError(f"Planet {planet_name} is outside the finder projection")
        if planet_name != "Moon" or moon_bbox is None:
            ax.scatter([planet_point[0]], [planet_point[1]], s=115, marker="o",
                       facecolors=TARGET_YELLOW, edgecolors=TARGET_YELLOW, linewidths=1.6, zorder=10)
        place_body_notation(
            ax, planet_name, planet_point, occupied_labels, target=True,
            obstacle_segments=figure_segments + asterism_segments + boundary_segments,
            marker_radius_points=0 if planet_name == "Moon" and moon_bbox is not None else math.sqrt(115) / 2 + 1.6 / 2,
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
            if body_name != "Moon" or moon_bbox is None:
                ax.scatter([point[0]], [point[1]], s=58, marker="o",
                           facecolors="none", edgecolors=TEXT, linewidths=1.2, zorder=8)
                occupied_labels.append(marker_obstacle_bbox(ax, point, 58, 1.2))
            place_body_notation(
                ax, body_name, point, occupied_labels, color=TEXT, fontsize=9,
                obstacle_segments=figure_segments + asterism_segments + boundary_segments,
            )
    for symbol, name, point in visible_ecliptic_signs(center, xmin, xmax, ymin, ymax):
        place_ecliptic_notation(
            ax, symbol, name, point, occupied_labels,
            obstacle_segments=figure_segments + asterism_segments,
        )
    label_coordinate_grid(ax, coordinate_grid, occupied_labels)
    for name, color, _, segments in reference_lines:
        if segments:
            start, end = segments[len(segments) // 2]
            point = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            place_label(ax, name, point, occupied_labels, color=color, fontsize=8,
                        obstacle_segments=figure_segments + asterism_segments,
                        require_clear=True)
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
    if spec.get("overview"):
        overview_ax.set_title(title + " — Aldebaran guide", color=TEXT, fontsize=14, pad=12)
        ax.text(0.5, 0.98, "Low-power telescope inset", transform=ax.transAxes,
                ha="center", va="top", fontsize=8, color=TEXT)
    else:
        ax.set_title(title, color=TEXT, fontsize=14, pad=12)
    title_ax = overview_ax if spec.get("overview") else ax
    mixed_title = title_ax.title.get_text()
    replacements = {}
    for name, abbreviation in ((figure_constellation, figure_abbreviation),
                               (planet_constellation, planet_abbreviation)):
        if name:
            _, names = constellation_names(name, abbreviation)
            replacements[name] = names["mixed"]
    if replacements:
        pattern = "|".join(re.escape(name) for name in sorted(replacements, key=len, reverse=True))
        mixed_title = re.sub(pattern, lambda match: replacements[match.group(0)], mixed_title)
        title_ax.title.set_gid("constellation-title-greek")
        for mode, text in (("latin", title_ax.title.get_text()), ("mixed", mixed_title)):
            alternative = title_ax.text(
                *title_ax.title.get_position(), text, transform=title_ax.title.get_transform(),
                color=TEXT, fontsize=14, ha="center", va="baseline",
            )
            alternative.set_gid(f"constellation-title-{mode}")
    kilroy = datetime.now(timezone.utc).strftime("Kilroy: Artwork · %Y-%m-%d %H:%M:%S UTC")
    stamp_ax = overview_ax if spec.get("overview") else ax
    stamp_ax.text(0.995, 1.015, kilroy, transform=stamp_ax.transAxes, ha="right", va="bottom", fontsize=6, color=TEXT)
    if spec.get("overview"):
        ax.text(0.5, 0.02, "North up · East ←   → West", transform=ax.transAxes,
                ha="center", va="bottom", fontsize=6, color=TEXT)
    else:
        ax.text(0.5, -0.035, "East ←                                      → West",
                transform=ax.transAxes, ha="center", va="top", fontsize=8, color=TEXT)
    legend_entries = []
    for ref in dict.fromkeys(figure_refs + ([target_ref] if target_ref else [])):
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
    legend_lines = []
    if legend:
        # SVG text does not automatically wrap long Matplotlib legend strings.
        # Keep complete entries together and bound the saved SVG's canvas.
        current = ""
        for entry in legend:
            candidate = f"{current}   ·   {entry}" if current else entry
            if current and len(candidate) > 70:
                legend_lines.append(current)
                current = entry
            else:
                current = candidate
        if current:
            legend_lines.append(current)
    if any(name == "Ecliptic" and segments for name, _, _, segments in reference_lines):
        legend_lines.extend((
            "Ecliptic ticks: 30° sign boundaries; longer tick: 0° Aries.",
            "Sign boundaries differ from constellation boundaries.",
        ))
    if legend_lines:
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
        spine.set_visible(bool(spec.get("overview")))
        if spec.get("overview"):
            spine.set_edgecolor(TEXT)
            spine.set_linewidth(1.2)
    output.parent.mkdir(parents=True, exist_ok=True)
    if has_planet and planet_name == "Moon" and moon_snapshot:
        draw_moon_closeup(ax, moon_snapshot,
                          figure_segments + asterism_segments + boundary_segments)
    fig.savefig(output, format="svg", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    add_constellation_notation(output)
    make_svg_responsive(output)


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


