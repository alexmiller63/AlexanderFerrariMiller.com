#!/usr/bin/env python3
"""Render Sky Notes stellar finders from accepted renderer specs.

This renderer is deliberately separate from the legacy reference-finder renderer.
It obeys the Sky Notes visual contract: blue constellation figures, green
asterisms, yellow open target circles, and no target arrows. Geometry is
consumed exactly as supplied by the generated spec; it is never inferred.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt

# This script lives in tools/, while the established stellar-rendering helpers
# live at repository root.  Add that root explicitly so direct execution from
# GitHub Actions resolves the shared renderer deterministically.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from render_stellar_finders import load_hyg, marker_area, project, spherical_center, star_index

NIGHT = "#071423"
STAR = "#f7f7f2"
TEXT = "#f3f5f7"
FIGURE_BLUE = "#5c8fe8"
ASTERISM_GREEN = "#59c86d"
TARGET_YELLOW = "#ffd84d"


def complete_index(stars):
    idx = star_index(stars)
    for star in sorted(stars, key=lambda item: item.mag):
        if star.proper:
            idx.setdefault(star.proper, star)
    return idx


def refs_from_paths(paths):
    return {ref for path in paths for ref in path}


def draw_path(ax, path, idx, center, color, linewidth):
    points = [project(idx[ref].ra_deg, idx[ref].dec_deg, *center) for ref in path]
    points = [point for point in points if point is not None]
    if len(points) >= 2:
        ax.plot(
            [point[0] for point in points],
            [point[1] for point in points],
            color=color,
            linewidth=linewidth,
            alpha=0.95,
            zorder=2,
        )


def render(spec: dict, stars, output: Path) -> None:
    idx = complete_index(stars)
    figure_paths = spec.get("figure_paths") or []
    asterisms = spec.get("asterisms") or []
    target_ref = spec["target"]

    refs = refs_from_paths(figure_paths) | {target_ref}
    for asterism in asterisms:
        refs |= refs_from_paths(asterism.get("paths") or [])
    missing = sorted(ref for ref in refs if ref not in idx)
    if missing:
        raise RuntimeError("Configured stars not found: " + ", ".join(missing))

    center_stars = [idx[ref] for ref in refs_from_paths(figure_paths) | {target_ref}]
    center = spherical_center(center_stars)
    projected_geometry = [
        project(idx[ref].ra_deg, idx[ref].dec_deg, *center)
        for ref in refs
    ]
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
        ax.scatter(
            [item[0] for item in visible],
            [item[1] for item in visible],
            s=[marker_area(item[2].mag, 7) for item in visible],
            color=STAR,
            zorder=1,
        )

    for path in figure_paths:
        draw_path(ax, path, idx, center, FIGURE_BLUE, 2.7)
    for asterism in asterisms:
        for path in asterism.get("paths") or []:
            draw_path(ax, path, idx, center, ASTERISM_GREEN, 3.2)

    target = idx[target_ref]
    target_xy = project(target.ra_deg, target.dec_deg, *center)
    if target_xy is None:
        raise RuntimeError(f"Target {target_ref!r} is outside the projection")
    ax.scatter(
        [target_xy[0]],
        [target_xy[1]],
        s=210,
        facecolors="none",
        edgecolors=TARGET_YELLOW,
        linewidths=2.6,
        zorder=8,
    )
    ax.annotate(
        target.proper or target_ref,
        target_xy,
        xytext=(14, 0),
        textcoords="offset points",
        ha="left",
        va="center",
        fontsize=10,
        color=TEXT,
        bbox=dict(facecolor=NIGHT, edgecolor="none", pad=0.8),
        zorder=9,
    )

    ax.set_title(spec.get("chart_title") or f"{target.proper or target_ref} Finder", color=TEXT, fontsize=14, pad=12)
    ax.text(
        0.5,
        -0.035,
        "East ←                                      → West",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8,
        color=TEXT,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output, format="svg", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("hyg_catalog", type=Path)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    import json

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    render(spec, load_hyg(args.hyg_catalog), args.output)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
