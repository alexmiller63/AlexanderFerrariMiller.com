"""Reconciled asterism geometry must be complete, explicit, and identity-stable."""
import json
from pathlib import Path
import tempfile
import unittest

from build_martz_macrobert_registry import asterism_records, read_asterism_paths
from enrich_martz_macrobert_coordinates import load_coordinates, enrich_vertex

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "asterism-figure-paths.json"


class AsterismGeometryTests(unittest.TestCase):
    def test_cached_coordinates_fill_missing_hips_without_overriding_hyg(self):
        with tempfile.TemporaryDirectory() as directory:
            hyg = Path(directory) / "hyg.csv"
            cache = Path(directory) / "hip.csv"
            hyg.write_text("hip,ra,dec,mag\n1,2,3,4\n")
            cache.write_text("hip,ra_h,dec_deg\n1,9,9\n55203,11.3031,31.5308\n")
            stars = load_coordinates(hyg, cache)
            self.assertEqual(stars[1]["ra_h"], 2)
            vertex = {"catalog": "HIP", "id": 55203}
            enrich_vertex(vertex, stars, "test")
            self.assertEqual(vertex["ra_h"], 11.3031)
            self.assertEqual(vertex["dec_deg"], 31.5308)
            self.assertEqual(vertex["coordinate_source"], "reference-data/hipparcos/figure-stars.csv")

    def test_all_28_permanent_identities_have_drawable_geometry(self):
        records = asterism_records(ROOT / "asterism-member-coordinates.csv", SOURCE)
        self.assertEqual({r["id"] for r in records.values()}, set(range(1362, 1390)))
        self.assertTrue(all(r["geometry_status"] == "accepted-paths" and r["paths"] for r in records.values()))

    def test_existing_drawings_keep_their_edges(self):
        built = json.loads((ROOT / "finder-geometry/martz-macrobert.json").read_text())["asterisms"]
        rebuilt = asterism_records(ROOT / "asterism-member-coordinates.csv", SOURCE)
        for key, old in built.items():
            with self.subTest(key=key):
                self.assertEqual([[v["id"] for v in p] for p in old["paths"]],
                                 [[v["id"] for v in p] for p in rebuilt[key]["paths"]])

    def read_modified_source(self, change):
        source = json.loads(SOURCE.read_text())
        change(source["asterisms"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paths.json"
            path.write_text(json.dumps(source))
            return read_asterism_paths(path)

    def test_display_name_does_not_define_identity(self):
        def rename(records):
            records["Renamed Sickle"] = records.pop("Sickle of Leo")
        self.assertEqual(self.read_modified_source(rename)[1369], read_asterism_paths(SOURCE)[1369])

    def test_missing_or_duplicate_ids_are_rejected(self):
        with self.assertRaises(RuntimeError):
            self.read_modified_source(lambda r: r.pop("Sickle of Leo"))
        with self.assertRaises(RuntimeError):
            self.read_modified_source(lambda r: r["Sickle of Leo"].update(id=1362))

    def test_no_figure_requires_explicit_status_and_reason(self):
        def figureless(records):
            records["Sickle of Leo"].update(geometry_status="no-figure", paths=[], reason="Explicit test declaration")
        self.assertEqual(self.read_modified_source(figureless)[1369], [])
        with self.assertRaises(RuntimeError):
            self.read_modified_source(lambda r: r["Sickle of Leo"].update(paths=[]))


if __name__ == "__main__":
    unittest.main()
