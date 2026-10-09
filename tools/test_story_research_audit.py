"""Research preflight must not confuse catalogue fallbacks with complete accounts."""
import tempfile
import unittest
from pathlib import Path

from audit_story_research import coverage, research_quality
from fixed_object_stories import baseline_story, read_story


class ResearchAuditTests(unittest.TestCase):
    def test_researched_accounts_are_ready(self):
        for collection, fixed_id in [("beta-stars", 698), ("special-stars", 594),
                                     ("alpha-stars", 717), ("alpha-stars", 718)]:
            with self.subTest(fixed_id=fixed_id):
                self.assertEqual(research_quality(read_story(collection, fixed_id)), [])

    def test_catalogue_fallback_still_needs_research(self):
        self.assertTrue(research_quality(baseline_story(717)))

    def test_repeated_identity_is_researched_once_across_weeks(self):
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "index.html"
            page.write_text('<div data-fixed-object-id="698"></div>'
                            '<div data-fixed-object-id="26"></div>'
                            '<div data-fixed-object-id="698"></div>')
            result = coverage([("2026-W01", page), ("2026-W02", page)])
            self.assertEqual(result["ready"], 1)
            self.assertEqual(result["needs_research"], 1)
            self.assertEqual(len(result["objects"]), 2)
            self.assertEqual(result["objects"][0]["weeks"], ["2026-W01", "2026-W02"])
            self.assertFalse(result["complete"])

    def test_missing_calendar_is_not_reported_as_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            result = coverage([("2026-W03", Path(directory) / "missing.html")])
            self.assertFalse(result["complete"])
            self.assertEqual(result["missing_calendar_pages"], ["2026-W03"])


if __name__ == "__main__":
    unittest.main()
