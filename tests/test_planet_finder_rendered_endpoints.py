"""Check drawable endpoints against the visible Greek circles."""
from datetime import date
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import planet_finder_rendering as rendering
from planet_finder_geometry import FinderMode
from planet_finder_validation import validate_layout
from test_planet_finder_anchor_hairpins import published, MODES


def draw(monkeypatch, rows, mode=FinderMode.GREEK):
    monkeypatch.setattr(rendering, 'layout', lambda *args, **kwargs: rows)
    return list(ET.fromstring(rendering.render(2026, 6, date(2026, 2, 2), mode, [])))


@pytest.mark.parametrize('week', range(1, 54))
def test_greek_leaders_reach_circles_and_preserve_routes(monkeypatch, week):
    rows = published(week, FinderMode.GREEK, 'greek-symbols')
    original = [(row[:4], list(row[4])) for row in rows]
    elements = draw(monkeypatch, rows)
    paths = [[tuple(map(float, point.split(','))) for point in element.attrib['points'].split()]
             for element in elements if element.tag.endswith('polyline')]
    circles = [element.attrib for element in elements
               if element.tag.endswith('circle') and element.attrib['r'] == '29']
    for row, path, circle in zip(rows, paths, circles):
        center = (float(circle['cx']), float(circle['cy']))
        # A historical route may already finish inside the opaque circle;
        # its visible stroke is clipped by the circle drawn over it.
        if math.dist(row[4][-1], center) > 29:
            assert math.dist(path[-1], center) == pytest.approx(29, abs=0.15)
        else:
            assert path[-1] == row[4][-1]
        assert path[:-1] == row[4][:-1]
        assert center == (row[3].x, row[3].y)
    assert [(row[:4], row[4]) for row in rows] == original
    # Historical layouts may already fail today's validator. No newly
    # extended terminal segment may invalidate a previously valid layout.
    if validate_layout(FinderMode.GREEK, rows)[0]:
        adjusted = [(*row[:4], path) for row, path in zip(rows, paths)]
        assert validate_layout(FinderMode.GREEK, adjusted)[0]


@pytest.mark.parametrize('mode,suffix', MODES[1:])
def test_text_modes_preserve_drawable_geometry(monkeypatch, mode, suffix):
    rows = published(6, mode, suffix)
    elements = draw(monkeypatch, rows, mode)
    paths = [element.attrib['points'] for element in elements if element.tag.endswith('polyline')]
    assert paths == [' '.join(f'{x:.1f},{y:.1f}' for x, y in row[4]) for row in rows]
