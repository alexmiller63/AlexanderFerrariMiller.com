#!/usr/bin/env python3
"""Mechanically move _solve_order into planet_finder_search.py.

Fail closed if expected source boundaries or the temporary fallback have changed.
No algorithm changes.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "tools" / "generate_planet_finders.py"
SEARCH = ROOT / "tools" / "planet_finder_search.py"


def main():
    gen = GEN.read_text(encoding="utf-8")
    search = SEARCH.read_text(encoding="utf-8")
    start_marker = "def _solve_order("
    end_marker = "\ndef generate_week("

    if gen.count(start_marker) != 1 or gen.count(end_marker) != 1:
        raise SystemExit("Refusing extraction: solver/generate_week boundary is not unique")
    if "def _solve_order(" in search:
        raise SystemExit("Refusing extraction: solver already exists in search module")

    start = gen.index(start_marker)
    end = gen.index(end_marker, start)
    solver = gen[start:end].rstrip() + "\n\n"

    fallback = '''        try:\n            try:\n                solver = _solve_order\n            except NameError:\n                from generate_planet_finders import _solve_order as solver\n            outcome = solver(\n'''
    direct = '''        try:\n            outcome = _solve_order(\n'''
    if search.count(fallback) != 1:
        raise SystemExit("Refusing extraction: expected fallback not found exactly once")

    dependency_imports = '''from planet_finder_validation import validate_layout\nfrom planet_finder_geometry import (\n    W, H, CX, CY, RO, RI,\n    LABEL_RIM_CLEARANCE, LABEL_COLLISION_PADDING,\n    IMMUTABLE_LEADER_CLEARANCE, PLACED_LABEL_LEADER_CLEARANCE,\n    LEADER_TO_LEADER_CLEARANCE, LEADER_RIM_CLEARANCE,\n    LABEL_LENGTH, PREFERRED_LABEL_RADII, EXPANDED_LABEL_RADII, ROUTE_RADII,\n    SIGNS, BODY_SYMBOLS, BODY_NAMES, CANONICAL,\n    DEFAULT_CANDIDATE_LAYOUTS, DEFAULT_MAX_NODE_CANDIDATES,\n    DEFAULT_MAX_SEARCH_SECONDS,\n    FinderMode, Body, Box,\n    xy, boxes_overlap, segment_hits_box, point_segment_distance,\n    segments_too_close, leaders_too_close, leader_hits_zodiac_rim, minimum_leader_separation,\n    label_size, reserved_boxes, candidate_positions,\n    legal_candidate_positions, route,\n)\n'''
    if "from planet_finder_validation import validate_layout" not in search:
        anchor = "from dataclasses import dataclass\n"
        if search.count(anchor) != 1:
            raise SystemExit("Refusing extraction: import anchor is not unique")
        search = search.replace(anchor, anchor + "\n" + dependency_imports, 1)

    layout_marker = "def layout(\n"
    if search.count(layout_marker) != 1:
        raise SystemExit("Refusing extraction: layout boundary is not unique")
    pos = search.index(layout_marker)
    new_search = search[:pos] + solver + search[pos:]
    new_search = new_search.replace(fallback, direct, 1)
    new_gen = gen[:start] + gen[end + 1:]

    if "def _solve_order(" in new_gen:
        raise SystemExit("Verification failed: solver remains in generator")
    if new_search.count("def _solve_order(") != 1:
        raise SystemExit("Verification failed: expected exactly one solver in search module")
    if "from generate_planet_finders import _solve_order" in new_search:
        raise SystemExit("Verification failed: fallback dependency remains")
    if "def generate_week(" not in new_gen or "def layout(" not in new_search:
        raise SystemExit("Verification failed: orchestration/search entry point missing")

    GEN.write_text(new_gen, encoding="utf-8")
    SEARCH.write_text(new_search, encoding="utf-8")
    print("Extracted _solve_order into planet_finder_search.py")


if __name__ == "__main__":
    main()
