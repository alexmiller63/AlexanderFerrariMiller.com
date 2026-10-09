"""Catalog completeness, composite identity, and cache-expansion regressions."""
import collections
import copy
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fixed_sky_annual as annual
import populate_calendar as astronomy
import populate_fixed_sky as fixed
from almanack_calendar import CalendarEvent, ensure_calendar_metadata, get_event_records, set_events
from calendar_fixed_object_ids import patch_text
from scaffold_almanack_weeks import page


class CompleteCalendarTests(unittest.TestCase):
    def test_all_catalog_rows_are_scheduled_once_per_coverage_year(self):
        records = annual._source_records()
        counts = collections.Counter(source for source, *_ in records)
        self.assertEqual(counts["messier"], 110)
        self.assertEqual(counts["caldwell"], 109)
        self.assertEqual(counts["finest_ngc"], 112)
        self.assertEqual(counts["special-star"], 24)
        identities = {( "fixed", fid) if fid is not None else (source, key)
                      for source, key, _, fid in records}
        self.assertEqual(len(identities), 531)

    def test_overlapping_catalogs_share_one_event_and_keep_designations(self):
        events = fixed.page_date_map(2026)
        for records in events.values():
            identities = [(r.fixed_object_id, r.catalog_target_key) for r in records]
            self.assertEqual(len(identities), len(set(identities)))
        fid = fixed.catalog_target_fixed_object_id("caldwell", "C2")
        records = [r for values in events.values() for r in values if r.fixed_object_id == fid]
        self.assertEqual(len(records), 1)
        self.assertIn("C2", records[0].html)
        self.assertIn("Finest NGC 110", records[0].html)

    def test_astronomy_and_identity_passes_preserve_composite_target(self):
        monday = dt.date.fromisocalendar(2026, 7, 1)
        target = CalendarEvent("Sirius and Sirius B", catalog_target_key="special-star:sirius-b")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "2026/W07/index.html"
            path.parent.mkdir(parents=True)
            text = page(2026, 7, monday)
            text = text.replace("<tbody></tbody>", "<tbody>" + "<tr><td>—</td><td>—</td><td>—</td></tr>" * 7 + "</tbody>", 1)
            text = ensure_calendar_metadata(text, path)
            text, found = set_events(text, monday, [target])
            self.assertTrue(found)
            path.write_text(text)
            ingresses, _, _ = astronomy.annual_calendar(2026)
            astronomy.patch_page(path, ingresses, {})
            updated, _ = patch_text(path.read_text())
            records = get_event_records(updated, monday)
            self.assertEqual(records, [target])

    def test_existing_annual_cache_fills_missing_catalog_row(self):
        data = copy.deepcopy(annual._load_table())
        interval = next(r for r in data["coverage"] if r["coverage_year"] == 2026)
        removed = next(r for r in interval["objects"] if r["source"] == "caldwell" and r["key"] == "C4")
        interval["objects"].remove(removed)
        old = {(r["source"], r["key"]): r for r in interval["objects"]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "coverage.json"
            path.write_text(json.dumps(data))
            with patch.object(annual, "TABLE", path):
                result = annual.ensure_coverage(2026)
        current = {(r["source"], r["key"]): r for r in result["objects"]}
        self.assertIn(("caldwell", "C4"), current)
        self.assertEqual(len(current), len(old) + 1)
        for key, value in old.items():
            self.assertEqual(current[key], value)


if __name__ == "__main__":
    unittest.main()
