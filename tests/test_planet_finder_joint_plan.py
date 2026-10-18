"""Regression checks for one complete placement shared by all three modes."""
import csv
import math
from pathlib import Path
import re
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from planet_finder_geometry import CANONICAL, CX, CY, FinderMode, alignment_groups
from planet_finder_joint_plan import plan_universal_layout
from planet_finder_search import layout
from planet_finder_validation import validate_layout

W17 = {
    'Neptune': 2.894, 'Mercury': 7.189, 'Saturn': 7.870, 'Mars': 7.905,
    'Sun': 29.933, 'Ceres': 44.066, 'Venus': 54.923, 'Uranus': 59.677,
    'Moon': 64.792, 'Jupiter': 107.510, 'Pluto': 305.445,
}
MODES = (FinderMode.GREEK, FinderMode.ENGLISH, FinderMode.MIXED)


def selected_bodies():
    signs = '♈♉♊♋♌♍♎♏♐♑♒♓'
    with (ROOT / 'weekly-ephemeris-2026.csv').open(encoding='utf-8', newline='') as file:
        rows = {int(row['iso_week'][-2:]): row for row in csv.DictReader(file)}
    selected = {17: [(name.lower(), name, W17[name]) for name in CANONICAL]}
    # Stored CSV positions have arcminute precision. This test checks the
    # placement solver; full-regression CI separately calculates exact kernels.
    for week in (20, 25, 39):
        values = []
        for name in CANONICAL:
            match = re.fullmatch(r'(.) (\d+)°(\d+)′', rows[week][name.lower()])
            longitude = signs.index(match[1]) * 30 + int(match[2]) + int(match[3]) / 60
            values.append((name.lower(), name, longitude))
        selected[week] = values
    return selected


class JointPlacementTests(unittest.TestCase):
    def test_selected_weeks_share_a_complete_valid_ordered_plan(self):
        for week, bodies in selected_bodies().items():
            started = time.monotonic()
            with self.subTest(week=week):
                shared = None
                for mode in MODES:
                    result = layout(mode, bodies, target_solutions=1,
                                    budget={'max_node_candidates': 200, 'max_seconds': 45},
                                    context_label=f'joint-plan-W{week:02d}')
                    self.assertEqual([row[1] for row in result], [row[1] for row in bodies])
                    self.assertEqual(len(result), 11)
                    valid, errors = validate_layout(mode, result)
                    self.assertTrue(valid, errors)
                    if shared is None:
                        shared = result
                    else:
                        self.assertEqual(result, shared)
                    boxes = {row[1]: row[3] for row in result}
                    for group in alignment_groups(bodies):
                        reference = group[0][2] - 90
                        angles = [((math.degrees(math.atan2(CY - boxes[name].y,
                                                          boxes[name].x - CX)) - 180)
                                   % 360 - reference) % 360 for _, name, _ in group]
                        self.assertEqual(angles, sorted(angles))
                # Cached paths are copied; mutating a returned path must not
                # alter the stored common plan for the next notation mode.
                first_point = shared[0][4][0]
                shared[0][4][0] = (-999, -999)
                fresh = plan_universal_layout(bodies, time.monotonic() + 1)
                self.assertEqual(fresh[0][4][0], first_point)
                # Confirm the independent validator rejects a damaged layout.
                damaged = list(fresh)
                row = damaged[1]
                damaged[1] = (*row[:3], damaged[0][3], row[4])
                self.assertFalse(validate_layout(FinderMode.GREEK, damaged)[0])
                print(f'W{week:02d}: shared ordered plan PASS {time.monotonic()-started:.3f}s',
                      flush=True)

    def test_expired_deadline_does_not_start_a_search(self):
        bodies = [(name.lower(), name, index * 31.5) for index, name in enumerate(CANONICAL)]
        with self.assertRaises(TimeoutError):
            plan_universal_layout(bodies, time.monotonic() - 1)


if __name__ == '__main__':
    unittest.main()
