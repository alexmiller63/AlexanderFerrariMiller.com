#!/usr/bin/env python3
"""One-shot repair: allow close leader anchors to fan apart without weakening downstream clearance."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_geometry.py")
text = TARGET.read_text(encoding="utf-8")

old = '''def leaders_too_close(path, existing_paths, clearance: float = LEADER_TO_LEADER_CLEARANCE) -> bool:
    """Reject a proposed leader that grazes or crosses an existing leader."""
    return any(
        segments_too_close(path[i], path[i + 1], other[j], other[j + 1], clearance)
        for other in existing_paths
        for i in range(len(path) - 1)
        for j in range(len(other) - 1)
    )
'''
new = '''def leaders_too_close(path, existing_paths, clearance: float = LEADER_TO_LEADER_CLEARANCE) -> bool:
    """Reject leader crossings/grazes after unavoidable close-anchor escape.

    Two astronomical anchors can legitimately be closer than the rendered
    leader clearance (or coincide in the conjunction limit).  Their leaders
    must be allowed to fan apart from that common neighborhood.  Once the
    corresponding first segments have escaped beyond the initial close-anchor
    condition, ordinary leader-to-leader clearance applies unchanged.
    """
    for other in existing_paths:
        close_anchors = math.hypot(path[0][0] - other[0][0], path[0][1] - other[0][1]) < clearance
        for i in range(len(path) - 1):
            for j in range(len(other) - 1):
                if close_anchors and i == 0 and j == 0:
                    # Shared/nearby origins are imposed by the sky geometry.
                    # Do not mistake that unavoidable initial proximity for a
                    # layout collision; all later segment pairs remain strict.
                    continue
                if segments_too_close(path[i], path[i + 1], other[j], other[j + 1], clearance):
                    return True
    return False
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: leaders_too_close block did not match exactly once")
text = text.replace(old, new, 1)
TARGET.write_text(text, encoding="utf-8")

TEST = Path("tests/test_planet_finder_leader_geometry.py")
test_text = '''import sys
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
'''
TEST.write_text(test_text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Made leader clearance anchor-aware: only the first-segment pair is exempt when anchors "
    "are already closer than clearance; all downstream crossing/graze checks remain strict. "
    "Added focused regression tests. Repair Once is now OFF."
)
