#!/usr/bin/env python3
"""One-shot diagnostic: trace Sun's missing widest candidate at the 1-degree boundary."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_geometry.py")
text = TARGET.read_text(encoding="utf-8")

old = '''def legal_candidate_positions(longitude: float, w: float, h: float, reserved: list[Box], displacement_scale: float = 2.0, diagnostic: dict | None = None):
    for x, y in candidate_positions(longitude, displacement_scale):
        box = Box(x, y, w, h)
        reserved_hits = [i for i, obstacle in enumerate(reserved) if boxes_overlap(box, obstacle, LABEL_COLLISION_PADDING)]
        if reserved_hits:
            if diagnostic is not None:
                diagnostic["immutable_reserved"] = diagnostic.get("immutable_reserved", 0) + 1
                by_obstacle = diagnostic.setdefault("immutable_reserved_by_obstacle", {})
                for i in reserved_hits:
                    by_obstacle[i] = by_obstacle.get(i, 0) + 1
                diagnostic.setdefault("immutable_candidate_audit", []).append((x, y, "reserved", tuple(reserved_hits)))
            continue
        rim_limit = RI - LABEL_RIM_CLEARANCE
        if any(math.hypot(px - CX, py - CY) >= rim_limit for px in (box.left, box.right) for py in (box.top, box.bottom)):
            if diagnostic is not None:
                diagnostic["immutable_rim"] = diagnostic.get("immutable_rim", 0) + 1
                diagnostic.setdefault("immutable_candidate_audit", []).append((x, y, "rim", ()))
            continue
        yield x, y, box
'''
new = '''def legal_candidate_positions(longitude: float, w: float, h: float, reserved: list[Box], displacement_scale: float = 2.0, diagnostic: dict | None = None):
    # Diagnostic only: for the Venus/Sun ladder, capture the first canonical
    # candidate before immutable filtering and its exact fate.  At 2deg the
    # Sun's first candidate survives; at 1deg it disappears from the legal
    # pool.  This trace identifies the rejecting immutable constraint without
    # changing candidate generation, legality, or ordering.
    trace_first = diagnostic is not None and abs(longitude - 101.0) < 1e-9
    first = True
    for x, y in candidate_positions(longitude, displacement_scale):
        box = Box(x, y, w, h)
        reserved_hits = [i for i, obstacle in enumerate(reserved) if boxes_overlap(box, obstacle, LABEL_COLLISION_PADDING)]
        if reserved_hits:
            if trace_first and first:
                diagnostic["sun_1deg_first_candidate_trace"] = {
                    "x": x, "y": y, "w": w, "h": h,
                    "result": "reserved", "reserved_hits": tuple(reserved_hits),
                    "corner_radii": tuple(
                        math.hypot(px - CX, py - CY)
                        for px in (box.left, box.right)
                        for py in (box.top, box.bottom)
                    ),
                }
            if diagnostic is not None:
                diagnostic["immutable_reserved"] = diagnostic.get("immutable_reserved", 0) + 1
                by_obstacle = diagnostic.setdefault("immutable_reserved_by_obstacle", {})
                for i in reserved_hits:
                    by_obstacle[i] = by_obstacle.get(i, 0) + 1
                diagnostic.setdefault("immutable_candidate_audit", []).append((x, y, "reserved", tuple(reserved_hits)))
            first = False
            continue
        rim_limit = RI - LABEL_RIM_CLEARANCE
        corner_radii = tuple(
            math.hypot(px - CX, py - CY)
            for px in (box.left, box.right)
            for py in (box.top, box.bottom)
        )
        if any(radius >= rim_limit for radius in corner_radii):
            if trace_first and first:
                diagnostic["sun_1deg_first_candidate_trace"] = {
                    "x": x, "y": y, "w": w, "h": h,
                    "result": "rim", "rim_limit": rim_limit,
                    "corner_radii": corner_radii,
                }
            if diagnostic is not None:
                diagnostic["immutable_rim"] = diagnostic.get("immutable_rim", 0) + 1
                diagnostic.setdefault("immutable_candidate_audit", []).append((x, y, "rim", ()))
            first = False
            continue
        if trace_first and first:
            diagnostic["sun_1deg_first_candidate_trace"] = {
                "x": x, "y": y, "w": w, "h": h,
                "result": "legal", "rim_limit": rim_limit,
                "corner_radii": corner_radii,
            }
        first = False
        yield x, y, box
'''

if text.count(old) != 1:
    raise SystemExit("Safety stop: legal_candidate_positions block did not match exactly once")
text = text.replace(old, new, 1)
TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Added diagnostic-only trace for the Sun's first canonical candidate at lambda=101deg. "
    "No candidate generation, legality, geometry, ordering, or search behavior changed. "
    "Repair Once is now OFF."
)
