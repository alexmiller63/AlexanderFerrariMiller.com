"""Identity regression checks: labels must not define objects or geometry."""
import unittest

import populate_sky_notes_by_date as notes
import populate_sky_notes_artwork_by_date as artwork
from fixed_object_stories import _routes_for
from object_identity import asterism_identity, require_fixed_object_id
from sky_note_descriptors import build_descriptors, _deep_sky_descriptor, _guiding_star_hops, _core_asterisms


class IdentityTests(unittest.TestCase):
    def test_all_core_asterisms_have_permanent_ids(self):
        records = _core_asterisms()
        self.assertEqual({r["id"] for r in records}, set(range(1362, 1390)))
        for record in records:
            asterism_identity(record["id"])
            for member in record["member_fixed_object_ids"]:
                require_fixed_object_id(member)

    def test_asterism_numeric_identity_survives_display_rename(self):
        entry = dict(notes.ASTERISMS["Leo"], name="A different display label")
        resolved = notes.canonical_asterism(entry)
        self.assertEqual(resolved["id"], 1369)
        self.assertEqual(resolved["geometry_key"], "asterism-sickle-of-leo")

    def test_descriptors_use_numeric_ids_without_double_prefix(self):
        for con, star_id, expected in (("Leo", 47, "1369"), ("Ori", 32, "1365"), ("Sgr", 94, "1372")):
            with self.subTest(con=con):
                records = build_descriptors([], [{"planet": "Mars", "star": "Renamed guide",
                    "star_fixed_object_id": star_id, "constellation": con,
                    "asterism": "Renamed landmark", "asterism_id": int(expected)}],
                    notes.load_bright_stars(), notes.CONSTELLATION_NAMES, notes.ASTERISMS)
                pattern = next(r for r in records if r["type"] == "asterism")
                self.assertEqual(pattern["id"], expected)
                self.assertEqual(pattern["geometry_key"], asterism_identity(expected)["geometry_key"])
                self.assertTrue(pattern["geometry"]["paths"])

    def test_routes_select_permanent_targets(self):
        self.assertEqual(_guiding_star_hops(60)[0]["id"], "big-dipper-arcturus-spica")
        self.assertEqual(_routes_for(25)[0]["id"], "orions-belt-aldebaran")
        self.assertEqual(_guiding_star_hops(384, "deep-sky-object")[0]["id"], "northern-cross-sadr-m29")

    def test_artwork_owner_uses_id_despite_renamed_label(self):
        payload = {"fixed_sky": [{"fixed_object_id": 384, "name": "M29", "type": "deep-sky"}]}
        descriptor = {"week": "2026-W10", "targets": [{"fixed_object_id": 384,
            "name": "Renamed cluster", "type": "deep-sky"}]}
        self.assertEqual(artwork.artwork_owner_identity(payload, descriptor)["fixed_object_id"], 384)

    def test_artwork_guide_uses_id_despite_renamed_label(self):
        spec = {"target": "Renamed guide", "figure_paths": [], "asterisms": [],
                "guide_objects": [{"fixed_object_id": 60, "name": "Renamed guide"}]}
        result = artwork.attach_fixed_object_ids(spec)
        self.assertEqual(result["guide_anchor_identity"]["fixed_object_id"], 60)
        self.assertEqual(result["guide_anchor_identity"]["renderer_ref"], "HIP 65474")

    def test_unknown_objects_cannot_create_name_derived_identity(self):
        with self.assertRaises(RuntimeError):
            _deep_sky_descriptor("Invented catalog object")
        with self.assertRaises(RuntimeError):
            require_fixed_object_id(999999)


if __name__ == "__main__":
    unittest.main()
