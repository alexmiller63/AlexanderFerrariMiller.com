"""Conservative cross-mode geometry envelope for Planet Finder preplanning.

This module is intentionally side-effect-free.  The existing per-mode solver
remains unchanged until shared-placement regression tests establish correctness.
"""
from __future__ import annotations

from planet_finder_geometry import Box, CANONICAL, FinderMode, label_size, reserved_boxes


def modes():
    """All supported presentation modes in their canonical order."""
    return tuple(FinderMode)


def shared_label_size(name: str) -> tuple[float, float]:
    """Smallest axis-aligned envelope containing each mode's label size."""
    if name not in CANONICAL:
        raise ValueError(f"Unknown Planet Finder body: {name}")
    dimensions = [label_size(mode, name) for mode in modes()]
    return max(width for width, _ in dimensions), max(height for _, height in dimensions)


def shared_reserved_boxes() -> list[Box]:
    """Conservative union of immutable obstacles in every notation mode.

    The obstacle lists include the same three central annotations followed by
    the twelve zodiac signs.  We preserve their separate rectangles rather
    than inventing an oversized bounding rectangle across different positions.
    """
    return [box for mode in modes() for box in reserved_boxes(mode)]


def shared_label_box(name: str, x: float, y: float) -> Box:
    """A mode-independent centered label box suitable for proposal screening."""
    width, height = shared_label_size(name)
    return Box(x, y, width, height)
