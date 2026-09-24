"""Rim-anchor search support for Planet Finder leaders.

A leader may attach at any angular position around the inner rim.  Rim anchors
are not exclusive: two or more leaders may use the identical point.  The
leader-to-leader clearance rule begins only after an initial inward escape from
the rim, so a shared anchor is not itself a collision.
"""
from __future__ import annotations

import math

from planet_finder_geometry import CX, CY, RI, LEADER_TO_LEADER_CLEARANCE, segments_too_close

# Search the complete rim deterministically. One-degree resolution gives every
# integer member of the 360-degree array; refinement can later be inserted
# between these samples without changing the contract.
RIM_ANCHOR_ANGLES = tuple(float(deg) for deg in range(360))

# Leaders sharing or nearly sharing a rim anchor need room to diverge before
# ordinary 8-pixel clearance is enforced.
RIM_ESCAPE_DISTANCE = 16.0


def rim_anchor(angle: float) -> tuple[float, float]:
    """Return the point on the inner rim at ``angle`` degrees."""
    theta = math.radians(angle % 360.0)
    return CX + RI * math.cos(theta), CY + RI * math.sin(theta)


def rim_escape_point(angle: float, distance: float = RIM_ESCAPE_DISTANCE) -> tuple[float, float]:
    """Return an inward point used to end the shared-anchor escape zone."""
    theta = math.radians(angle % 360.0)
    radius = RI - distance
    return CX + radius * math.cos(theta), CY + radius * math.sin(theta)


def anchor_candidates(preferred_angle: float | None = None):
    """Yield all 360 rim anchors, preferred direction first when supplied.

    No occupancy state is accepted or consulted: coincident anchors are legal.
    """
    if preferred_angle is None:
        order = RIM_ANCHOR_ANGLES
    else:
        p = int(round(preferred_angle)) % 360
        order = (float(p),) + tuple(float(d) for d in range(360) if d != p)
    for angle in order:
        yield angle, rim_anchor(angle), rim_escape_point(angle)


def _same_point(a, b, tolerance: float = 1e-6) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= tolerance


def leaders_too_close_after_rim_escape(path, existing_paths, clearance: float = LEADER_TO_LEADER_CLEARANCE) -> bool:
    """Apply leader clearance after the shared rim-anchor escape zone.

    If two paths have the same first point, their first segments are allowed to
    coincide/cross while leaving that common rim anchor.  All later segment
    pairs retain the normal clearance.  Different anchors receive the normal
    rule immediately.
    """
    for other in existing_paths:
        shared_anchor = bool(path and other and _same_point(path[0], other[0]))
        for i in range(len(path) - 1):
            for j in range(len(other) - 1):
                if shared_anchor and i == 0 and j == 0:
                    continue
                if segments_too_close(path[i], path[i + 1], other[j], other[j + 1], clearance):
                    return True
    return False
