#!/usr/bin/env python3
"""Move _solve_order from generate_planet_finders.py into planet_finder_search.py.

Mechanical, idempotent refactor only. No algorithm changes.
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

    if start_marker not in gen:
        if "def _solve_order(" in search:
            print("_solve_order already extracted")
            return
        raise SystemExit("_solve_order not found in generator")

    start = gen.index(start_marker)
    end = gen.index(end_marker, start)
    solver = gen[start:end].rstrip() + "\n\n"
    gen = gen[:start] + gen[end + 1:]

    # The extracted solver owns geometry/search validation dependencies.
    dependency_imports = '''from planet_finder_validation import validate_layout\nfrom planet_finder_geometry import (\n    W, H, CX, CY, RO, RI,\n    LABEL_RIM_CLEARANCE, LABEL_COLLISION_PADDING,\n    IMMUTABLE_LEADER_CLEARANCE, PLACED_LABEL_LEADER_CLEARANCE,\n    LEADER_TO_LEADER_CLEARANCE, LEADER_RIM_CLEARANCE,\n    LABEL_LENGTH, PREFERRED_LABEL_RADII, EXPANDED_LABEL_RADII, ROUTE_RADII,\n    SIGNS, BODY_SYMBOLS, BODY_NAMES, CANONICAL,\n    DEFAULT_CANDIDATE_LAYOUTS, DEFAULT_MAX_NODE_CANDIDATES,\n    DEFAULT_MAX_SEARCH_SECONDS,\n    FinderMode, Body, Box,\n    xy, boxes_overlap, segment_hits_box, point_segment_distance,\n    segments_too_close, leaders_too_close, leader_hits_zodiac_rim,\n    label_size, reserved_boxes, candidate_positions,\n    legal_candidate_positions, route,\n)\n'''
    if "from planet_finder_validation import validate_layout" not in search:
        anchor = "from dataclasses import dataclass\n"
        search = search.replace(anchor, anchor + "\n" + dependency_imports, 1)

    # Put the fixed-order engine before layout(), which controls it.
    layout_marker = "def layout(\n"
    if layout_marker not in search:
        raise SystemExit("layout() marker not found in planet_finder_search.py")
    pos = search.index(layout_marker)
    search = search[:pos] + solver + search[pos:]

    fallback = '''        try:\n            try:\n                solver = _solve_order\n            except NameError:\n                from generate_planet_finders import _solve_order as solver\n            outcome = solver(\n'''
    direct = '''        try:\n            outcome = _solve_order(\n'''
    if fallback not in search:
        raise SystemExit("expected _solve_order fallback block not found")
    search = search.replace(fallback, direct, 1)

    GEN.write_text(gen, encoding="utf-8")
    SEARCH.write_text(search, encoding="utf-8")
    print("Extracted _solve_order into planet_finder_search.py")


if __name__ == "__main__":
    main()
