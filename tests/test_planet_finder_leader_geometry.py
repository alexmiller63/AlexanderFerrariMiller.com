import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from planet_finder_geometry import leaders_too_close


def test_nearby_anchors_may_fan_apart():
    first = [(0.0, 0.0), (20.0, 10.0)]
    second = [(4.0, 0.0), (20.0, -10.0)]
    assert not leaders_too_close(second, [first], clearance=8.0)


def test_coincident_anchors_may_fan_apart():
    first = [(0.0, 0.0), (20.0, 10.0)]
    second = [(0.0, 0.0), (20.0, -10.0)]
    assert not leaders_too_close(second, [first], clearance=8.0)


def test_downstream_crossing_remains_illegal_after_close_anchor_escape():
    first = [(0.0, 0.0), (20.0, 10.0), (40.0, -10.0)]
    second = [(4.0, 0.0), (20.0, -10.0), (40.0, 10.0)]
    assert leaders_too_close(second, [first], clearance=8.0)


def test_downstream_graze_remains_illegal_after_close_anchor_escape():
    first = [(0.0, 0.0), (20.0, 10.0), (40.0, 10.0)]
    second = [(4.0, 0.0), (20.0, -10.0), (40.0, 4.0)]
    assert leaders_too_close(second, [first], clearance=8.0)


def test_separate_anchors_keep_normal_first_segment_clearance():
    first = [(0.0, 0.0), (20.0, 0.0)]
    second = [(9.0, 0.0), (20.0, 1.0)]
    assert leaders_too_close(second, [first], clearance=8.0)
