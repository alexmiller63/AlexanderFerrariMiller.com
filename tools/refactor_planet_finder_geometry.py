#!/usr/bin/env python3
"""One-shot safe extraction of Planet Finder geometry/search support.

This script is intentionally conservative: it only edits when the expected
source markers are present, writes a new support module, and leaves validation
and commit/push to the GitHub Actions workflow.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_planet_finders.py"
MODULE = ROOT / "tools" / "planet_finder_geometry.py"

START = "W = H = 1400\n"
END = "\ndef _solve_order("

IMPORT_ANCHOR = "from planet_finder_search import DepthNodeBudgetExhausted, SearchOutcome\n"
GEOMETRY_IMPORT = """from planet_finder_geometry import (
    W, H, CX, CY, RO, RI,
    LABEL_RIM_CLEARANCE, LABEL_COLLISION_PADDING,
    IMMUTABLE_LEADER_CLEARANCE, PLACED_LABEL_LEADER_CLEARANCE,
    LEADER_TO_LEADER_CLEARANCE, LEADER_RIM_CLEARANCE,
    LABEL_LENGTH, PREFERRED_LABEL_RADII, EXPANDED_LABEL_RADII, ROUTE_RADII,
    SIGNS, BODY_SYMBOLS, BODY_NAMES, CANONICAL,
    DEFAULT_CANDIDATE_LAYOUTS, DEFAULT_MAX_NODE_CANDIDATES,
    DEFAULT_MAX_SEARCH_SECONDS,
    FinderMode, Body, Box,
    xy, boxes_overlap, segment_hits_box, point_segment_distance,
    segments_too_close, leaders_too_close, leader_hits_zodiac_rim,
    label_size, reserved_boxes, candidate_positions,
    legal_candidate_positions, route,
)
"""

PRELUDE = '''"""Planet Finder geometry, labels, routing, and presentation support.

Extracted mechanically from generate_planet_finders.py. Keep this module
behavior-preserving; the generator remains the orchestration entry point.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto

from populate_ephemeris import TARGETS

'''


def main() -> None:
    text = GENERATOR.read_text(encoding="utf-8")

    if GEOMETRY_IMPORT in text:
        if not MODULE.exists():
            raise SystemExit("geometry import exists but support module is missing")
        print("Planet Finder geometry extraction already applied.")
        return

    if MODULE.exists():
        raise SystemExit("support module already exists; refusing ambiguous rewrite")
    if IMPORT_ANCHOR not in text:
        raise SystemExit("expected planet_finder_search import anchor not found")

    start = text.find(START)
    if start < 0:
        raise SystemExit("geometry block start marker not found")

    end = text.find(END, start)
    if end < 0:
        raise SystemExit("_solve_order boundary not found")

    block = text[start:end]
    required = (
        "class FinderMode",
        "class Body",
        "class Box",
        "def xy(",
        "def boxes_overlap(",
        "def segment_hits_box(",
        "def point_segment_distance(",
        "def segments_too_close(",
        "def leaders_too_close(",
        "def leader_hits_zodiac_rim(",
        "def label_size(",
        "def reserved_boxes(",
        "def candidate_positions(",
        "def legal_candidate_positions(",
        "def route(",
    )
    missing = [marker for marker in required if marker not in block]
    if missing:
        raise SystemExit(f"refusing extraction; expected markers missing: {missing}")

    # The search solver must remain in the generator for this extraction.
    if "def _solve_order(" in block:
        raise SystemExit("refusing extraction; solver crossed geometry boundary")

    MODULE.write_text(PRELUDE + block.lstrip("\n"), encoding="utf-8")

    rewritten = text[:start] + text[end + 1 :]
    rewritten = rewritten.replace(
        IMPORT_ANCHOR,
        IMPORT_ANCHOR + GEOMETRY_IMPORT,
        1,
    )
    GENERATOR.write_text(rewritten, encoding="utf-8")

    print(f"Extracted {block.count(chr(10)) + 1} source lines into {MODULE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
