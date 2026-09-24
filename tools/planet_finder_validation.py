"""Independent completed-layout validation for Planet Finder."""
from __future__ import annotations

import math

from planet_finder_geometry import (
    CX, CY, RI, LABEL_RIM_CLEARANCE, LABEL_COLLISION_PADDING,
    IMMUTABLE_LEADER_CLEARANCE, PLACED_LABEL_LEADER_CLEARANCE,
    reserved_boxes, boxes_overlap, segment_hits_box,
    leader_hits_zodiac_rim, leaders_too_close,
)

def validate_layout(mode: str, result) -> tuple[bool, list[str]]:
    """Recheck a completed layout independently before rendering it."""
    errors = []
    reserved = reserved_boxes(mode)
    boxes = [row[3] for row in result]
    paths = [row[4] for row in result]

    # Labels must not overlap reserved annotations/zodiac labels or each other.
    for i, box in enumerate(boxes):
        name = result[i][1]
        for j, obstacle in enumerate(reserved):
            if boxes_overlap(box, obstacle, LABEL_COLLISION_PADDING):
                errors.append(f"{name}: label overlaps reserved obstacle {j}")
        for j in range(i):
            if boxes_overlap(box, boxes[j], LABEL_COLLISION_PADDING):
                errors.append(f"{name}: label overlaps {result[j][1]}")

    # Every leader must remain clear of every label except its own endpoint.
    for i, path in enumerate(paths):
        name = result[i][1]
        for j, box in enumerate(boxes):
            if i == j:
                continue
            for a, b in zip(path, path[1:]):
                if segment_hits_box(a, b, box, PLACED_LABEL_LEADER_CLEARANCE):
                    errors.append(f"{name}: leader crosses {result[j][1]} label")
                    break
        for j, obstacle in enumerate(reserved):
            # The route solver permits an initial escape from an obstacle
            # containing the body's anchor. Do not reinterpret that legal
            # escape as a post-layout collision; later segments must be clear.
            for seg_index, (a, b) in enumerate(zip(path, path[1:])):
                # Match route() exactly: only the 3 fixed center annotations
                # may permit an initial escape. Zodiac labels are never escape
                # obstacles, even when the body anchor lies inside their box.
                if seg_index == 0 and j < 3 and (
                    obstacle.left - IMMUTABLE_LEADER_CLEARANCE <= a[0] <= obstacle.right + IMMUTABLE_LEADER_CLEARANCE and
                    obstacle.top - IMMUTABLE_LEADER_CLEARANCE <= a[1] <= obstacle.bottom + IMMUTABLE_LEADER_CLEARANCE
                ):
                    continue
                if segment_hits_box(a, b, obstacle, IMMUTABLE_LEADER_CLEARANCE):
                    errors.append(f"{name}: leader crosses reserved obstacle {j}")
                    break

    # The inner zodiac rim is protected geometry. Recheck this independently
    # after search so no stale/future routing bug can render a leader touching
    # or crossing the circle.
    for i, path in enumerate(paths):
        if leader_hits_zodiac_rim(path):
            errors.append(f"{result[i][1]}: leader collides with inner zodiac border")

    # Leaders are mutually exclusive geometry.  This is intentionally a
    # second, independent check after proposal-time rejection so a stale or
    # future search-state bug can never render crossing/grazing leaders.
    for i, path in enumerate(paths):
        for j in range(i):
            if leaders_too_close(path, [paths[j]]):
                errors.append(
                    f"{result[i][1]}: leader crosses or grazes {result[j][1]} leader"
                )

    # Recheck the hard inner-rim rule independently of candidate generation.
    rim_limit = RI - LABEL_RIM_CLEARANCE
    for i, box in enumerate(boxes):
        if any(
            math.hypot(px - CX, py - CY) >= rim_limit
            for px in (box.left, box.right)
            for py in (box.top, box.bottom)
        ):
            errors.append(f"{result[i][1]}: label collides with inner zodiac border")

    return not errors, errors

