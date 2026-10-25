"""Publication checks against every stored event, without external artwork."""
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from eclipse_artwork import circles, svg
from eclipse_editorial import record_downloads, render_page


class ArtworkTests(unittest.TestCase):
    def test_catalog_publication(self):
        events = json.loads((ROOT / 'generated/eclipse-catalog/eclipses-2025-2036.json').read_text())['eclipses']
        for event in events:
            with self.subTest(event=event['id']):
                drawing = ET.fromstring(svg(event))
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
