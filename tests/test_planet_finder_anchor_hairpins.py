"""Exercise anchor cleanup against the actual published drawable geometry."""
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from planet_finder_geometry import BODY_SYMBOLS, CANONICAL, CX, CY, Box, FinderMode
from planet_finder_makeup import straighten_anchor_hairpins, uncross_labels
from planet_finder_validation import validate_layout

MODES = ((FinderMode.GREEK, 'greek-symbols'),
         (FinderMode.ENGLISH, 'latin'), (FinderMode.MIXED, 'mixed-learner'))


def published(week, mode, suffix, fixture=False):
    path = (ROOT / 'tests/fixtures/planet-finder-w06-mixed-anchor-hairpin.svg' if fixture
            else ROOT / f'almanack/2026/W{week:02d}/finders/planet-finder-{suffix}.svg')
    elements = list(ET.parse(path).getroot())
    if sum(element.tag.endswith('polyline') for element in elements) != len(CANONICAL):
        pytest.skip('Historical ten-body artwork predates the current generator')
    shapes = [element.attrib for element in elements
              if (element.tag.endswith('rect') and 'rx' in element.attrib)
              or (element.tag.endswith('circle') and float(element.attrib['r']) == 29)]
    rows = []
    for index, element in enumerate(elements):
        if not element.tag.endswith('polyline'):
            continue
        name = CANONICAL[len(rows)]
        shape = shapes[len(rows)]
        path = [tuple(map(float, point.split(','))) for point in element.attrib['points'].split()]
        if mode == FinderMode.GREEK:
            box = Box(float(shape['cx']), float(shape['cy']), 64, 64)
        else:
            w, h = float(shape['width']), float(shape['height'])
            box = Box(float(shape['x']) + w / 2, float(shape['y']) + h / 2, w, h)
        longitude = (math.degrees(math.atan2(CY - path[0][1], path[0][0] - CX)) - 180) % 360
        rows.append((BODY_SYMBOLS[name.lower()], name, longitude, box, path))
    return rows


@pytest.mark.parametrize('mode,suffix', [MODES[2]])
def test_w06_mars_hairpin_is_removed_without_moving_labels(mode, suffix):
    original = published(6, mode, suffix, fixture=True)
    fixed = uncross_labels((mode,), original)
    old = next(row for row in original if row[1] == 'Mars')
    new = next(row for row in fixed if row[1] == 'Mars')
    assert len(old[4]) == 5
    assert new[4] == [old[4][0], *old[4][3:]]
    assert validate_layout(mode, fixed)[0]
    for before, after in zip(original, fixed):
        assert before[:4] == after[:4]
        assert before[4][0] == after[4][0]
    assert published(6, mode, suffix, fixture=True) == original
    assert straighten_anchor_hairpins((mode,), fixed) == fixed


@pytest.mark.parametrize('week', range(1, 54))
@pytest.mark.parametrize('mode,suffix', MODES)
def test_published_year_preserves_validity_and_placements(week, mode, suffix):
    original = published(week, mode, suffix)
    valid, _ = validate_layout(mode, original)
    fixed = straighten_anchor_hairpins((mode,), original)
    if valid:
        assert validate_layout(mode, fixed)[0]
    else:
        assert fixed == original
    for before, after in zip(original, fixed):
        assert before[:4] == after[:4]
        assert before[4][0] == after[4][0]
        assert before[4][-1] == after[4][-1]
    assert straighten_anchor_hairpins((mode,), fixed) == fixed


def test_blocked_shortcuts_preserve_original(monkeypatch):
    import planet_finder_makeup as makeup
    original = published(6, FinderMode.MIXED, 'mixed-learner', fixture=True)
    # Reject changed paths to exercise the cosmetic fallback explicitly.
    monkeypatch.setattr(makeup, 'validate_layout', lambda mode, rows: (rows == original, []))
    assert straighten_anchor_hairpins((FinderMode.MIXED,), original) == original


def test_shortcut_cannot_introduce_a_crossing_even_with_escape_allowance(monkeypatch):
    import planet_finder_makeup as makeup
    # Both shortcuts cross the neighboring first segment at x=1. The
    # original hairpin passes above it, so keep the original route.
    rows = [('a', 'A', 0, Box(120, 30, 10, 10),
             [(0, 0), (0, 20), (2, 0), (100, 20), (120, 30)]),
            ('b', 'B', 0, Box(1, 1, 1, 1), [(1, -1), (1, 1)])]
    monkeypatch.setattr(makeup, 'validate_layout', lambda mode, rows: (True, []))
    assert straighten_anchor_hairpins((FinderMode.MIXED,), rows) == rows


def test_shared_plan_requires_every_mode_to_accept_shortcut(monkeypatch):
    import planet_finder_makeup as makeup
    rows = published(6, FinderMode.MIXED, 'mixed-learner', fixture=True)
    monkeypatch.setattr(makeup, 'validate_layout',
                        lambda mode, trial: (trial == rows or mode != FinderMode.ENGLISH, []))
    assert straighten_anchor_hairpins(tuple(mode for mode, _ in MODES), rows) == rows
