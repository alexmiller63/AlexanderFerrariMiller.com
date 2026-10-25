"""Regression checks for offline meteor shower generation. Run: python -m unittest discover -s tests -p 'test_meteor_showers.py'"""
import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "generate_meteor_showers.py"
spec = importlib.util.spec_from_file_location("meteor_generator", MODULE)
meteor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(meteor)

class MeteorGeneratorTests(unittest.TestCase):
    def test_no_unreviewed_shower_advertised(self):
        registry, events, calendar, notes = meteor.build({})
        self.assertEqual(len(events), len(registry) * 3)
        self.assertEqual(calendar, [])
        self.assertEqual(notes, {})
        self.assertTrue(all(not event["recommended"] for event in events))

    def test_verified_worthwhile_only(self):
        reviews = {
            "PER-2026": {"annual_peak_verified": True, "peak_date": "2026-08-13",
                         "naked_eye_quality": "worthwhile", "source": "reviewed"},
            "GEM-2026": {"annual_peak_verified": False, "naked_eye_quality": "worthwhile"},
            "LYR-2026": {"annual_peak_verified": True, "peak_date": "2026-04-22",
                         "naked_eye_quality": "poor"},
        }
        _, events, calendar, notes = meteor.build(reviews)
        self.assertEqual([e["event_id"] for e in calendar], ["PER-2026"])
        self.assertIn("2026-08-10", notes)
        self.assertEqual(sum(e["recommended"] for e in events), 1)

    def test_unique_ids_and_years(self):
        _, events, _, _ = meteor.build({})
        self.assertEqual(len(events), len({e["id"] for e in events}))
        self.assertEqual({e["year"] for e in events}, {2025, 2026, 2027})

    def test_reject_wrong_year(self):
        with self.assertRaises(ValueError):
            meteor.build({"PER-2026": {"annual_peak_verified": True,
                                        "peak_date": "2027-08-12",
                                        "naked_eye_quality": "worthwhile"}})

if __name__ == "__main__":
    unittest.main()
