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

GREEK_SYMBOL_ORDER = "αβγδεζηθικλμνξοπρστυφχψω"
GREEK_ORDER = {symbol: rank for rank, symbol in enumerate(GREEK_SYMBOL_ORDER)}


def complete_index(stars):
    idx = star_index(stars)
    for star in sorted(stars, key=lambda item: item.mag):
        if star.proper:
            idx.setdefault(star.proper, star)
    return idx


def refs_from_paths(paths):
    return {ref for path in paths for ref in path}


def identity_index(spec):
    """Index hidden database identities by renderer alias and immutable ID."""
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
    """Return the authoritative normalized fixed-object record for an immutable ID."""
    path = REPO_ROOT / "database" / "fixed-objects.json"
    if not path.exists():
        raise RuntimeError(f"Fixed-object database is missing at {path.relative_to(REPO_ROOT)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for obj in payload.get("fixed_objects") or []:
        if obj.get("fixed_object_id") == fixed_id:
            return obj
    raise RuntimeError(f"Target fixed_object_id {fixed_id} is absent from fixed-object database")


def fixed_object_metadata(fixed_id, fallback=None):
    """Resolve display metadata and catalog position for any fixed object.

    Stellar guides come from the HYG renderer catalog. Deep-sky targets do not,
    so their canonical coordinates are taken from the normalized fixed-object
    database instead of being mistaken for one of the guide stars.
    """
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
    """Return a Greek Bayer designation, falling back to the pinned HYG star record."""
    stored = str(identity.get("bayer") or "").strip()
    if stored:
        return stored
    if star is None:
        return ""
    greek = greek_bayer_symbol(star.bayer)
    return " ".join(part for part in (greek, star.con) if part)


def chart_bayer_label(identity, star, figure_abbreviation):
    """Figure labels are Greek only; external-constellation stars add the IAU abbreviation."""
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
    """Legend is Greek letter plus proper name, when one exists."""
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

    # Artwork ownership is keyed by immutable fixed_object_id.  A stellar
    # owner also has a renderer_ref; a deep-sky owner deliberately does not.
    target_identity = spec.get("target_identity") or spec.get("artwork_owner_identity") or {}
    target_id = target_identity.get("fixed_object_id")
    if target_id is None:
        raise RuntimeError("Finder target must resolve through hidden fixed_object_id")

    target_star_identity = identities_by_id.get(target_id)
    target_ref = target_identity.get("renderer_ref") or (target_star_identity or {}).get("renderer_ref")
    if target_ref and target_ref not in idx:
        raise RuntimeError(f"Target renderer_ref {target_ref} is not present in coordinate catalog")

    # Guide-star geometry is independent of the fixed object being located.
    refs = refs_from_paths(figure_paths)
    if target_ref:
        refs.add(target_ref)
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

    figure_refs = []
    seen = set()
    for path in figure_paths:
        for ref in path:
            if ref not in seen:
                seen.add(ref)
                figure_refs.append(ref)
    figure_constellation = spec.get("name") or ""
    figure_abbreviation = str(target_meta.get("constellation_abbreviation") or "").strip()

    figure_points = []
    for ref in figure_refs:
        star = idx[ref]
        identity = identities_by_ref[ref]
        point = project(star.ra_deg, star.dec_deg, *center)
        if point is None:
            continue
        figure_points.append(point)
        # A stellar target receives its yellow target label below; do not label it twice.
        if identity.get("fixed_object_id") == target_id:
            continue
        label = chart_bayer_label(identity, star, figure_abbreviation)
        if label:
            ax.annotate(label, point, xytext=(5, 5), textcoords="offset points",
                        fontsize=9, color=TEXT, zorder=6)

    if figure_constellation and figure_points:
        ax.text(sum(x for x, _ in figure_points) / len(figure_points),
                sum(y for _, y in figure_points) / len(figure_points),
                figure_constellation, color=FIGURE_BLUE, fontsize=16,
                fontweight="bold", ha="center", va="center", zorder=5)

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
    target_chart_label = " ".join(part for part in (target_greek, target_name) if part)
    if not target_chart_label:
        target_chart_label = str(target_identity.get("name") or "Target")
    ax.annotate(target_chart_label, target_point, xytext=(14, 0), textcoords="offset points",
                ha="left", va="center", fontsize=10, color=TARGET_YELLOW,
                bbox=dict(facecolor=NIGHT, edgecolor="none", pad=0.8), zorder=9)

    title_const = str(target_meta.get("constellation_abbreviation") or "").strip()
    title_parts = [" ".join(part for part in (target_greek, title_const) if part)]
    if target_name:
        title_parts.append(target_name)
    title = ", ".join(part for part in title_parts if part)
    if figure_constellation:
        title += f", in {figure_constellation}"
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
        ax.text(0.5, -0.075, "   •   ".join(legend), transform=ax.transAxes,
                ha="center", va="top", fontsize=7, color=TEXT, wrap=True)

    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
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
