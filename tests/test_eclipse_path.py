"""Geometric invariants and real-kernel central-path integration."""
import json
import math
from pathlib import Path
from datetime import datetime
import tempfile
from unittest.mock import patch
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
from eclipse_engine import EARTH_RADIUS_KM, Vec3
from eclipse_path import axis_surface_point, central_path, split_track
from eclipse_editorial import render_visibility


class SurfaceIntersectionTests(unittest.TestCase):
    def test_hits_moon_facing_surface_not_far_side(self):
        moon = Vec3(384000, 0, 0)
        sun = Vec3(150000000, 0, 0)
        point = axis_surface_point(moon, sun)
        self.assertAlmostEqual(point.x, EARTH_RADIUS_KM)
        self.assertAlmostEqual(point.norm(), EARTH_RADIUS_KM)

    def test_miss_and_axis_pointing_away(self):
        self.assertIsNone(axis_surface_point(Vec3(384000, 20000, 0), Vec3(150000000, 20000, 0)))
        self.assertIsNone(axis_surface_point(Vec3(-384000, 0, 0), Vec3(150000000, 0, 0)))

    def test_dateline_does_not_draw_across_world(self):
        points = [{'longitude_deg': x, 'latitude_deg': 0, 'phase': 'total'}
                  for x in (175, 179, -179, -175)]
        self.assertEqual([len(s) for s in split_track(points)], [2, 2])


class KernelPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from kernel_eclipse_engine import KernelEclipseEngine
        cls.engine = KernelEclipseEngine(ROOT / 'star-almanack/assets/ephemera/de440s.bsp')
        events = json.loads((ROOT / 'generated/eclipse-catalog/eclipses-2025-2036.json').read_text())['eclipses']
        cls.hybrid = next(e for e in events if e['date_utc'] == '2031-11-14')

    def test_hybrid_track_contains_both_phases_and_valid_surface_points(self):
        track = central_path(self.engine, self.hybrid)
        self.assertEqual({p['phase'] for p in track['points']}, {'total', 'annular'})
        self.assertTrue(any(p['utc'] == self.hybrid['greatest_utc'] for p in track['points']))
        times = [p['utc'] for p in track['points']]
        self.assertEqual(times, sorted(set(times)))
        from skyfield.framelib import itrs
        import numpy as np
        for point in track['points'][::20]:
            t = self.engine.timescale.utc(datetime.fromisoformat(point['utc'].replace('Z', '+00:00')))
            lat, lon = map(math.radians, (point['latitude_deg'], point['longitude_deg']))
            earth_fixed = EARTH_RADIUS_KM * np.array([math.cos(lat)*math.cos(lon), math.cos(lat)*math.sin(lon), math.sin(lat)])
            observer = itrs.rotation_at(t).T @ earth_fixed
            moon = (self.engine.kernel['moon'] - self.engine.kernel['earth']).at(t).position.km - observer
            sun = (self.engine.kernel['sun'] - self.engine.kernel['earth']).at(t).position.km - observer
            # A center-line observer sees geometrically concentric Sun and Moon.
            self.assertLess(np.linalg.norm(np.cross(moon / np.linalg.norm(moon), sun / np.linalg.norm(sun))), 2e-6)
            self.assertLess(np.dot(earth_fixed, earth_fixed) - EARTH_RADIUS_KM**2, 0.001)

    def test_invalid_sample_step_is_rejected(self):
        for step in (0, -1, float('nan'), float('inf')):
            with self.subTest(step=step), self.assertRaises(ValueError):
                central_path(self.engine, self.hybrid, step)

    def test_publisher_exports_and_rerun_are_idempotent(self):
        import integrate_eclipses
        event = dict(self.hybrid, central_path=central_path(self.engine, self.hybrid))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / 'generated/eclipse-catalog/eclipses-2025-2036.json'
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({'eclipses': [event]}))
            with patch.object(integrate_eclipses, 'ROOT', root), patch.object(sys, 'argv', ['integrate', '--catalog', str(catalog)]):
                integrate_eclipses.main()
                first = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                integrate_eclipses.main()
                second = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(first, second)
            output = root / 'almanack/eclipses'
            self.assertIn('Latitude', (output / (event['id'] + '.html')).read_text())
            import csv
            with (output / (event['id'] + '-path.csv')).open() as f:
                self.assertEqual(len(list(csv.DictReader(f))), len(event['central_path']['points']))
            features = json.loads((output / (event['id'] + '-path.geojson')).read_text())['features']
            self.assertTrue(features)
            for feature in features:
                coords = feature['geometry']['coordinates']
                self.assertTrue(all(abs(a[0] - b[0]) <= 180 for a, b in zip(coords, coords[1:])))

    def test_noncentral_event_has_no_track(self):
        event = dict(self.hybrid, type='partial', contacts_utc='{}')
        self.assertEqual(central_path(self.engine, event)['points'], [])

    def test_display_uses_calculated_track_instead_of_reference_map(self):
        event = dict(self.hybrid, central_path=central_path(self.engine, self.hybrid),
                     visibility_reference={'map_url': 'https://example.invalid/borrowed.gif'})
        page = render_visibility(event)
        self.assertIn('Calculated central path', page)
        self.assertIn('<svg', page)
        self.assertIn('Latitude', page)
        self.assertNotIn('borrowed.gif', page)
        self.assertIn('spherical', page.lower())


if __name__ == '__main__':
    unittest.main()
