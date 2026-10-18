"""Exercise cosmetic swaps against the published W04 drawable geometry."""
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from planet_finder_geometry import BODY_SYMBOLS, CANONICAL, CX, CY, Box, FinderMode
from planet_finder_makeup import _paths_cross, uncross_labels
from planet_finder_validation import validate_layout


def published_layout(mode, suffix):
    elements = list(ET.parse(ROOT / f'almanack/2026/W04/finders/planet-finder-{suffix}.svg').getroot())
    rows = []
    for index, element in enumerate(elements):
        if not element.tag.endswith('polyline'):
            continue
        name = CANONICAL[len(rows)]
        shape = elements[index + 1].attrib
        path = [tuple(map(float, point.split(','))) for point in element.attrib['points'].split()]
        if mode == FinderMode.GREEK:
            box = Box(float(shape['cx']), float(shape['cy']), 64, 64)
        else:
            w, h = float(shape['width']), float(shape['height'])
            box = Box(float(shape['x']) + w / 2, float(shape['y']) + h / 2, w, h)
        longitude = (math.degrees(math.atan2(CY - path[0][1], path[0][0] - CX)) - 180) % 360
        rows.append((BODY_SYMBOLS[name.lower()], name, longitude, box, path))
    return rows


@pytest.mark.parametrize('mode,suffix', [(FinderMode.GREEK, 'greek-symbols'),
                                        (FinderMode.MIXED, 'mixed-learner')])
def test_w04_swap_removes_crossing_without_changing_escape_rule(mode, suffix):
    original = published_layout(mode, suffix)
    # The escape allowance intentionally accepts the original layout.
    assert validate_layout(mode, original)[0]
    by_name = {row[1]: row for row in original}
    assert _paths_cross(by_name['Moon'][4], by_name['Venus'][4])
    fixed = uncross_labels((mode,), original)
    assert validate_layout(mode, fixed)[0]
    assert not any(_paths_cross(row[4], other[4])
                   for i, row in enumerate(fixed) for other in fixed[:i])
    for old, new in zip(original, fixed):
        assert old[:3] == new[:3]
        assert old[4][0] == new[4][0]
        assert (old[3].w, old[3].h) == (new[3].w, new[3].h)
        destination = by_name[{'Moon': 'Venus', 'Venus': 'Moon'}.get(old[1], old[1])][3]
        assert (new[3].x, new[3].y) == (destination.x, destination.y)
    assert uncross_labels((mode,), fixed) == fixed
    assert published_layout(mode, suffix) == original


def test_uncrossed_layout_is_unchanged():
    original = uncross_labels((FinderMode.ENGLISH,), published_layout(FinderMode.ENGLISH, 'latin'))
    assert validate_layout(FinderMode.ENGLISH, original)[0]
    assert not any(_paths_cross(row[4], other[4])
                   for i, row in enumerate(original) for other in original[:i])
    assert uncross_labels((FinderMode.ENGLISH,), original) == original
