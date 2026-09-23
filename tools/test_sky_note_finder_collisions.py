#!/usr/bin/env python3
"""Regression checks for Sky Notes finder label collision geometry.

This deliberately exercises Matplotlib's rendered text extents.  It verifies
that our collision predicate detects a protected line crossing a label's true
bounding box; the production renderer can then use the same geometry when
choosing candidate positions.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


def rendered_bbox(ax, text, point=(0.5, 0.5), offset=(5, 5), fontsize=9):
    annotation = ax.annotate(
        text,
        point,
        xytext=offset,
        textcoords="offset points",
        fontsize=fontsize,
    )
    ax.figure.canvas.draw()
    return annotation, annotation.get_window_extent(renderer=ax.figure.canvas.get_renderer())


def segment_intersects_bbox(ax, start, end, bbox):
    """Return whether a data-coordinate segment crosses a display-coordinate bbox."""
    start_display = ax.transData.transform(start)
    end_display = ax.transData.transform(end)
    segment = Line2D(
        [start_display[0], end_display[0]],
        [start_display[1], end_display[1]],
    ).get_path()
    return segment.intersects_bbox(bbox, filled=False)


def main():
    fig, ax = plt.subplots(figsize=(8.2, 8.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    annotation, bbox = rendered_bbox(ax, "β", point=(0.5, 0.5), offset=(5, 5))

    # A protected figure segment through the rendered label must be rejected.
    inv = ax.transData.inverted()
    middle_y = (bbox.y0 + bbox.y1) / 2
    crossing_start = inv.transform((bbox.x0 - 20, middle_y))
    crossing_end = inv.transform((bbox.x1 + 20, middle_y))
    assert segment_intersects_bbox(ax, crossing_start, crossing_end, bbox), (
        "failed to detect constellation/asterism segment crossing rendered Bayer label"
    )

    # A remote segment must remain acceptable.
    remote_y = bbox.y1 + 100
    remote_start = inv.transform((bbox.x0 - 20, remote_y))
    remote_end = inv.transform((bbox.x1 + 20, remote_y))
    assert not segment_intersects_bbox(ax, remote_start, remote_end, bbox), (
        "collision predicate rejected geometry that is clear of rendered Bayer label"
    )

    annotation.remove()
    plt.close(fig)
    print("Sky Notes rendered-label collision geometry: PASS")


if __name__ == "__main__":
    main()
