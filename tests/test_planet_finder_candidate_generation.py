#!/usr/bin/env python3
"""Unit tests for Planet Finder candidate-admission invariants."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from generate_planet_finders import Box, legal_candidate_positions, route, reserved_boxes


def test_legal_candidate_positions_rejects_immutable_geometry():
    """Every admitted proposal must already clear reserved chart geometry and rim."""
    longitude = 13 + 44 / 60
    for mode, width, height in (
        ("greek", 64, 64),
        ("latin", 13 * len("Saturn") + 28, 50),
        ("mixed", max(132, 13 * len("Saturn") + 68), 50),
    ):
        reserved = reserved_boxes(mode)
        proposals = list(legal_candidate_positions(longitude, width, height, reserved))
        assert proposals, f"no legal Saturn proposals admitted in {mode} mode"
        for _, _, box in proposals:
            assert not any(
                __import__("generate_planet_finders").boxes_overlap(box, obstacle, 14)
                for obstacle in reserved
            ), f"reserved-geometry collision admitted in {mode}: {box}"
            rim_limit = __import__("generate_planet_finders").RI - 14
            assert all(
                __import__("math").hypot(px - __import__("generate_planet_finders").CX,
                                         py - __import__("generate_planet_finders").CY) < rim_limit
                for px in (box.left, box.right)
                for py in (box.top, box.bottom)
            ), f"rim-crossing proposal admitted in {mode}: {box}"


def test_route_rejects_anchor_inside_placed_body_label():
    """Another body's label is never an escape obstacle for this body's leader."""
    anchor = (700, 700)
    center = (900, 700)
    placed_label = Box(700, 700, 100, 100)
    diagnostic = {"elbows": {}}
    assert route(
        anchor,
        center,
        [placed_label],
        diagnostic=diagnostic,
        allow_initial_escape_count=0,
        prefix_cache={},
    ) is None
    assert diagnostic.get("anchor_blocked") == 1
