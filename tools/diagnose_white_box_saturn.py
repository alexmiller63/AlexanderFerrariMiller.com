#!/usr/bin/env python3
"""Diagnose why Saturn has no forward-check witness in the crowded white box."""
from __future__ import annotations

from planet_finder_geometry import (
    BODY_SYMBOLS, CANONICAL, FinderMode, RI, boxes_overlap, candidate_positions,
    label_size, leader_hits_zodiac_rim, leaders_too_close,
    legal_candidate_positions, reserved_boxes, route, segment_hits_box, xy,
)


def crowded_bodies(center=15.0, span=6.0):
    n = len(CANONICAL)
    start = center - span / 2
    step = span / (n - 1) if n > 1 else 0
    return [(BODY_SYMBOLS[name.lower()], name, (start + i * step) % 360.0)
            for i, name in enumerate(CANONICAL)]


def main():
    mode = FinderMode.GREEK
    bodies = crowded_bodies()
    reserved = reserved_boxes(mode)
    immutable_count = 3
    by_name = {name: (symbol, name, lon) for symbol, name, lon in bodies}
    sun = by_name["Sun"]
    saturn = by_name["Saturn"]

    _, _, sun_lon = sun
    sw, sh = label_size(mode, "Sun")
    sun_anchor = xy(sun_lon, RI - 5)

    print("WHITE BOX SATURN FORWARD-WITNESS GATE AUDIT", flush=True)
    sun_number = 0
    for _, _, sun_box in legal_candidate_positions(sun_lon, sw, sh, reserved, 2.0):
        sun_path = route(
            sun_anchor, (sun_box.x, sun_box.y), reserved,
            allow_initial_escape_count=immutable_count, prefix_cache={},
        )
        if sun_path is None or leader_hits_zodiac_rim(sun_path):
            continue
        sun_number += 1

        _, _, sat_lon = saturn
        w, h = label_size(mode, "Saturn")
        anchor = xy(sat_lon, RI - 5)
        counts = {
            "raw": 0, "box_overlap": 0, "leader_hits_label": 0,
            "route": 0, "leader_rim": 0, "leader_graze": 0, "witness": 0,
        }
        for _, _, box in legal_candidate_positions(sat_lon, w, h, reserved, 2.0):
            counts["raw"] += 1
            if boxes_overlap(box, sun_box, 14):
                counts["box_overlap"] += 1
                continue
            if any(segment_hits_box(sun_path[i], sun_path[i + 1], box, 10)
                   for i in range(len(sun_path) - 1)):
                counts["leader_hits_label"] += 1
                continue
            path = route(
                anchor, (box.x, box.y), [*reserved, sun_box],
                allow_initial_escape_count=immutable_count, prefix_cache={},
            )
            if path is None:
                counts["route"] += 1
                continue
            if leader_hits_zodiac_rim(path):
                counts["leader_rim"] += 1
                continue
            if leaders_too_close(path, [sun_path]):
                counts["leader_graze"] += 1
                continue
            counts["witness"] += 1

        print(
            f"SATURN-GATES after-sun#{sun_number} "
            f"sun=({sun_box.x:.1f},{sun_box.y:.1f}) " +
            " ".join(f"{k}={v}" for k, v in counts.items()),
            flush=True,
        )
        if counts["witness"]:
            print("SATURN-GATES RESULT: Saturn has a surviving witness for this Sun placement", flush=True)
        else:
            dominant = max((k for k in counts if k not in {"raw", "witness"}), key=counts.get)
            print(f"SATURN-GATES RESULT: no witness; dominant rejection={dominant} count={counts[dominant]}", flush=True)

        if sun_number >= 12:
            break

    if sun_number == 0:
        print("SATURN-GATES RESULT: no routable Sun placement found", flush=True)


if __name__ == "__main__":
    main()
