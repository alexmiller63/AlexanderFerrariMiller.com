"""Publication checks against every stored event, without external artwork."""
import json
import math
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from eclipse_artwork import circles, svg
from eclipse_editorial import record_downloads, render_page


class ArtworkTests(unittest.TestCase):
    def test_solar_numerical_charts(self):
        events = json.loads((ROOT / 'generated/eclipse-catalog/eclipses-2025-2036.json').read_text())['eclipses']
        for event in events:
            if event['kind'] != 'solar':
                continue
            with self.subTest(event=event['id']):
                drawing = ET.fromstring(svg(event))
                ns = '{http://www.w3.org/2000/svg}'
                self.assertIsNotNone(drawing.find(f'.//{ns}g[@id="shadow-coordinate-grid"]'))
                text = ''.join(drawing.itertext())
                self.assertIn('GLOBAL UTC TIMELINE', text)
                contacts = event['contacts_utc']
                if isinstance(contacts, str):
                    contacts = json.loads(contacts)
                for value in [event['greatest_utc'], *contacts.values()]:
                    if value:
                        self.assertIn(value[11:19], text)
                plotted = drawing.findall(ns+'circle')
                geometry = circles(event)
                scales = [float(c.attrib['r']) / shape[2] for c, shape in zip(plotted, geometry)]
                self.assertEqual(len(plotted), 3)
                self.assertLess(max(scales)-min(scales), .00001)
                self.assertAlmostEqual(float(plotted[0].attrib['cx'])-float(plotted[1].attrib['cx']),
                                       event['axis_distance_km']*scales[0], delta=.002)
                self.assertEqual(drawing.find(f'.//{ns}g[@id="timed-central-path"]') is not None,
                                 bool(event.get('central_path', {}).get('points')))

    def test_catalog_publication(self):
        events = json.loads((ROOT / 'generated/eclipse-catalog/eclipses-2025-2036.json').read_text())['eclipses']
        for event in events:
            with self.subTest(event=event['id']):
                drawing = ET.fromstring(svg(event))
                if event['kind'] == 'lunar':
                    text = ''.join(drawing.itertext())
                    self.assertIn('CONTACTS', text)
                    self.assertIn('VISIBILITY', text)
                    self.assertIn('North', text)
                    self.assertTrue(drawing.findall('.//{http://www.w3.org/2000/svg}polyline'))
                    from lunar_eclipse_chart import calculate
                    from eclipse_engine import MOON_RADIUS_KM
                    for point in calculate(event)['phases']:
                        phase = point['phase']
                        distance = math.hypot(point['x_km'], point['y_km'])
                        if phase in ('P1', 'P4'):
                            expected = point['penumbra_radius_km'] + MOON_RADIUS_KM
                        elif phase in ('U1', 'U4'):
                            expected = point['umbra_radius_km'] + MOON_RADIUS_KM
                        elif phase in ('U2', 'U3'):
                            expected = point['umbra_radius_km'] - MOON_RADIUS_KM
                        else:
                            expected = event['axis_distance_km']
                        self.assertAlmostEqual(distance, expected, delta=1.)
                else:
                    self.assertEqual(len(drawing.findall('{http://www.w3.org/2000/svg}circle')), 3)
                self.assertFalse(drawing.findall('.//{http://www.w3.org/2000/svg}image'))
                name = event['id'] + '-shadow.svg'
                self.assertIn(name, render_page(event))
                self.assertIn(name, record_downloads(event))
                self.assertNotIn('eclipse.gsfc.nasa.gov', render_page(event))
                if event['kind'] == 'lunar':
                    shapes = circles(event)
                    _, distance, moon, _ = shapes[-1]
                    umbra = shapes[1][2]
                    kind = ('penumbral' if distance-moon > umbra else
                            'partial' if distance+moon > umbra else 'total')
                    self.assertEqual(kind, event['type'])

    def test_invalid_geometry_fails_publication(self):
        for distance in (float('nan'), float('inf'), -1):
            with self.assertRaises(ValueError):
                svg(dict(kind='lunar', axis_distance_km=distance,
                         core_radius_km=4000, penumbra_margin_km=-10000))

    def test_topocentric_horizon(self):
        from lunar_eclipse_chart import above_horizon
        from eclipse_engine import EARTH_RADIUS_KM
        # Sub-lunar point, antipode, and the geometric parallax horizon.
        moon = [384000., 0., 0.]
        self.assertTrue(above_horizon(moon, 0., 0.))
        self.assertFalse(above_horizon(moon, 0., 180.))
        horizon = math.degrees(math.acos(EARTH_RADIUS_KM / 384000.))
        self.assertTrue(above_horizon(moon, 0., horizon-.01))
        self.assertFalse(above_horizon(moon, 0., horizon+.01))

