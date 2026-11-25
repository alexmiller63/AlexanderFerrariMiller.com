"""Contract tests for conservative cross-mode preplanning geometry."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pytest

from planet_finder_geometry import (
    CANONICAL, FinderMode, label_size, reserved_boxes, boxes_overlap,
)
from planet_finder_cross_mode import (
    modes, shared_label_size, shared_label_box, shared_reserved_boxes,
)


def test_all_modes_included():
    assert set(modes()) == set(FinderMode)


@pytest.mark.parametrize("name", CANONICAL)
def test_shared_label_encloses_every_mode(name):
    width, height = shared_label_size(name)
    for mode in FinderMode:
        mode_width, mode_height = label_size(mode, name)
        assert width >= mode_width
        assert height >= mode_height


@pytest.mark.parametrize("name", CANONICAL)
def test_shared_label_box_has_envelope_dimensions(name):
    width, height = shared_label_size(name)
    box = shared_label_box(name, 321, 456)
    assert (box.x, box.y, box.w, box.h) == (321, 456, width, height)


def test_reserved_obstacles_include_each_mode():
    shared = shared_reserved_boxes()
    for mode in FinderMode:
        for box in reserved_boxes(mode):
            assert box in shared


@pytest.mark.parametrize("name", CANONICAL)
def test_shared_clearance_implies_per_mode_clearance(name):
    # For a fixed center, the shared envelope is never smaller than any
    # per-mode label. Therefore an obstacle that misses the envelope also
    # misses the corresponding smaller label.
    x, y = 321, 456
    shared = shared_label_box(name, x, y)
    for mode in FinderMode:
        width, height = label_size(mode, name)
        from planet_finder_geometry import Box
        mode_box = Box(x, y, width, height)
        for obstacle in shared_reserved_boxes():
            if not boxes_overlap(shared, obstacle, 14):
                assert not boxes_overlap(mode_box, obstacle, 14)


def test_unknown_body_rejected():
    with pytest.raises(ValueError):
        shared_label_size("Unknown")
