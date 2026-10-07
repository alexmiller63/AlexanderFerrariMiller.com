"""Regression checks for facts, changing motion, angle wraps and both views."""
import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import populate_sky_notes_by_date as base
from planet_weekly_facts import WeekGeometry, build_weekly_facts, preserved_facts
from populate_sky_notes_descriptor_by_date import render_planet_treatments
from star_almanack_ephemeris import StarAlmanackEphemeris
from star_almanack_planets import load_weekly_longitudes

ROOT = Path(__file__).resolve().parents[1]

class WeeklyFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = StarAlmanackEphemeris()
        cls.stars = base.load_bright_stars()
        cls.yearly = load_weekly_longitudes(2026)
        cls.page = ROOT / 'almanack/2026/W01/index.html'
        routes = base.planetary_finder_relations(1, cls.yearly, cls.stars, cls.page)
        cls.facts = build_weekly_facts(2026, 1, cls.page, routes, base.PLANET_OBJECT_IDS, cls.model)
        cls.artworks = base.planetary_artwork_descriptors(2026, 1, [], routes)

    def test_preserved_symbol_headers_and_glare(self):
        facts = preserved_facts(self.page)
        self.assertEqual(set(facts), {'sun', *[k.lower() for k in base.PLANET_OBJECT_IDS]})
        self.assertTrue(facts['mercury']['solar_glare'])
        self.assertEqual(facts['pluto']['set'], '18:12')

    def test_complete_permanent_identity_and_phase(self):
        self.assertEqual(set(self.facts), set(base.PLANET_OBJECT_IDS.values()))
        for object_id, facts in self.facts.items():
            self.assertEqual(facts['object_id'], object_id)
            self.assertIsInstance(facts['guide_star_fixed_object_id'], int)
            self.assertTrue(0 <= facts['illuminated_percent'] <= 100)
        self.assertIn('below', self.facts[base.PLANET_OBJECT_IDS['Pluto']]['body'])
        self.assertEqual(self.facts[base.PLANET_OBJECT_IDS['Jupiter']]['motion'], 'retrograde')

    def test_close_pairs_are_symmetric(self):
        for object_id, facts in self.facts.items():
            for pair in facts['close_pairs']:
                reverse = self.facts[pair['object_id']]['close_pairs']
                self.assertIn({'object_id': object_id, 'name': facts['name'], 'separation_deg': pair['separation_deg']}, reverse)

    def test_station_and_wrap(self):
        geometry = WeekGeometry(self.model)
        start = datetime(2026, 3, 16, tzinfo=timezone.utc)
        stations = geometry.crossings(lambda t: geometry.velocity('mercury', t), start)
        self.assertEqual(len(stations), 1)
        station = stations[0]
        self.assertLess(geometry.velocity('mercury', station-timedelta(hours=1)), 0)
        self.assertGreater(geometry.velocity('mercury', station+timedelta(hours=1)), 0)
        self.assertEqual(geometry.crossings(lambda t: 179 if t < start+timedelta(hours=3) else -179, start), [])

    def test_both_views_have_facts_and_unique_anchors(self):
        payload = {'planet_finder_artworks': self.artworks, 'planet_weekly_facts': self.facts}
        wordy = render_planet_treatments(payload)
        highlights = render_planet_treatments(payload, highlights=True)
        for facts in self.facts.values():
            self.assertIn(facts['guide_star'], highlights)
            self.assertIn(facts['motion'], wordy)
            self.assertIn('illuminated', highlights)
        anchors = re.findall(r' id="([^"]+)"', wordy+highlights)
        self.assertEqual(len(anchors), len(set(anchors)))
        self.assertNotIn('No weekly orbital-condition', wordy+highlights)
        # Artwork publishing must retain the fact-bearing reference links.
        from publish_sky_note_artwork import PATHFINDER_LINK_RE
        self.assertEqual(PATHFINDER_LINK_RE.sub('', highlights), highlights)

if __name__ == '__main__':
    unittest.main()
