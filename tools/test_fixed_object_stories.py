"""Verify researched story routing and independent horizon boundary cases."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import fixed_object_stories as stories


class FixedObjectStoryTests(unittest.TestCase):
    def test_complete_status_requires_identity_sources_and_review_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "beta-stars").mkdir()
            path = root / "beta-stars/698.md"
            content = (
                "---\nfixed_object_id: 698\nstatus: complete\n"
                "research_checked: true\nfinder_checked: true\npublication_checked: true\n---\n"
                "# A researched star\n\nA useful dek.\n\nA researched account. Sources: https://example.org/paper\n"
            )
            with patch.object(stories, "STORIES_ROOT", root):
                path.write_text(content)
                self.assertEqual(stories.read_story("beta-stars", 698).status, "complete")
                for old, new in (("fixed_object_id: 698", "fixed_object_id: 699"),
                                 ("research_checked: true", "research_checked: false"),
                                 ("finder_checked: true", "finder_checked: false"),
                                 ("publication_checked: true", "publication_checked: false"),
                                 ("https://example.org/paper", "unrecorded source"),
                                 ("status: complete", "status: unknown")):
                    with self.subTest(field=old):
                        path.write_text(content.replace(old, new))
                        with self.assertRaises(RuntimeError):
                            stories.read_story("beta-stars", 698)

    def test_unmarked_curated_and_baseline_stories_remain_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "beta-stars").mkdir()
            (root / "beta-stars/698.md").write_text("# A written story\n\nA dek.\n\nA body.")
            with patch.object(stories, "STORIES_ROOT", root):
                self.assertEqual(stories.read_story("beta-stars", 698).status, "pending")
        self.assertEqual(stories.baseline_story(414).status, "pending")

    def test_week_report_deduplicates_objects_and_retains_unmapped_targets(self):
        from almanack_calendar import CalendarEvent, ensure_calendar_metadata, set_events
        from scaffold_almanack_weeks import page
        from story_completion import completion_report
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "2026/W01/index.html"
            path.parent.mkdir(parents=True)
            monday = date.fromisocalendar(2026, 1, 1)
            text = page(2026, 1, monday).replace("<tbody></tbody>", "<tbody>" + "<tr><td>—</td><td>—</td><td>—</td></tr>" * 7 + "</tbody>", 1)
            text = ensure_calendar_metadata(text, path)
            text, found = set_events(text, monday, [
                CalendarEvent("Same object", fixed_object_id=698),
                CalendarEvent("Other catalog name", fixed_object_id=698),
                CalendarEvent("Needs research", fixed_object_id=414),
                CalendarEvent("Unmapped composite", catalog_target_key="special-star:unmapped"),
                CalendarEvent("Full Moon"),
            ])
            self.assertTrue(found)
            path.write_text(text)
            (root / "beta-stars").mkdir()
            (root / "beta-stars/698.md").write_text(
                "---\nfixed_object_id: 698\nstatus: complete\nresearch_checked: true\n"
                "finder_checked: true\npublication_checked: true\n---\n"
                "# A star\n\nA dek.\n\nA body. Sources: https://example.org/research\n"
            )
            with patch.object(stories, "STORIES_ROOT", root):
                report = completion_report(path, 2026, 1)
            self.assertEqual((report["total"], report["complete"]), (3, 1))
            self.assertEqual(len(report["pending"]), 2)
            self.assertEqual({item["fixed_object_id"] for item in report["pending"]}, {414, None})
            self.assertEqual(report["pending"][1]["catalog_target_key"], "special-star:unmapped")
            self.assertFalse((root / "baseline").exists())

    def test_beta_reticuli_curated_story_reaches_reader_page(self):
        story = stories.read_story("beta-stars", 698)
        self.assertIn("hidden companion", story.hed)
        self.assertIn("1,918 days", story.body)
        self.assertIn("does not establish", story.body)
        self.assertIn("doi:10.1111/", story.body)
        self.assertNotIn("Calendar selected", story.body)
        self.assertEqual(story.artwork, "stellar-finder")
        self.assertGreaterEqual(len(story.body.split()), 500)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "beta-stars").mkdir()
            (root / "beta-stars" / "698.md").write_text(story.path.read_text())
            with patch.object(stories, "STORIES_ROOT", root):
                selected = stories.available_stories(698)
                self.assertEqual(len(selected), 1)
                self.assertEqual(selected[0].collection, "beta-stars")
                rendered = (root / "beta-stars" / "698.html").read_text()
                self.assertIn("1,918 days", rendered)
                self.assertIn("data-fixed-object-id=\"698\"", rendered)
                before = (root / "beta-stars" / "698.html").stat().st_mtime_ns
                stories.available_stories(698)
                self.assertEqual(before, (root / "beta-stars" / "698.html").stat().st_mtime_ns)

    def test_horizon_limits_at_default_latitude(self):
        for dec, expected in ((-64.8, "does not rise"), (-45, "does not rise"),
                              (0, "45° altitude"), (45, "circumpolar"),
                              (60, "75° altitude")):
            with self.subTest(dec=dec):
                text = " ".join(stories._stellar_observing_facts({"dec_deg": dec}))
                self.assertIn(expected, text)
                self.assertIn("excluding refraction", text)

    def test_weekly_wordy_includes_full_account_highlights_keep_hook(self):
        from populate_sky_notes_descriptor_by_date import render_linked_stories
        story = stories.read_story("beta-stars", 698)
        candidate = dict(fixed_object_id=698, collection=story.collection,
                         hed=story.hed, dek=story.dek, body=story.body,
                         url=story.public_url)
        wordy = render_linked_stories([candidate], elaborate=True)
        highlights = render_linked_stories([candidate])
        self.assertIn("1,918 days", wordy)
        self.assertIn("Sources:", wordy)
        self.assertNotIn("1,918 days", highlights)
        self.assertIn(story.dek, highlights)
        self.assertIn("../../../stories/beta-stars/698.html", wordy)

    def test_unknown_coordinates_do_not_invent_properties(self):
        self.assertEqual(stories._stellar_observing_facts({}), [])

    def test_catalogue_matches_permanent_identity_despite_display_name(self):
        meta = stories._fixed_object_meta(698)
        meta["name"] = "Renamed star"
        text = " ".join(stories._stellar_observing_facts(meta))
        self.assertIn("3.84", text)
        self.assertIn("does not rise", text)


if __name__ == "__main__":
    unittest.main()
