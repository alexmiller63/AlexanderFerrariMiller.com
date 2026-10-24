"""Recovered pilot sequence numbers must resolve through catalogue identities."""
import json
import unittest
from pathlib import Path

from tools.import_luna_pilot import PILOT, resolve


class PilotIdentityTests(unittest.TestCase):
    def test_all_ten_match_original_manifest_and_registry(self):
        root = Path(__file__).resolve().parents[1]
        catalogue = json.loads((root / "database/fixed-objects.json").read_text())
        manifest = json.loads((root / "research/luna-pilot-candidates.json").read_text())
        resolved = []
        for candidate in manifest:
            number = int(candidate["id"])
            hip = candidate["facts"].split("Registry identity: ", 1)[1].split(".", 1)[0]
            with self.subTest(pilot=number):
                self.assertEqual(PILOT[number][1], hip)
                resolved.append(resolve(catalogue, hip))
        self.assertEqual(len(resolved), 10)
        self.assertEqual(len(set(resolved)), 10)
        self.assertEqual(resolved[-2:], [9, 10])

    def test_ambiguous_and_missing_identities_are_rejected(self):
        record = {"source_key": "HIP 11767"}
        catalogue = {"fixed_objects": [
            {"fixed_object_id": ident, "source_records": [record]} for ident in [9, 999]
        ]}
        for hip in ["HIP 11767", "HIP 1176"]:
            with self.subTest(hip=hip), self.assertRaises(ValueError):
                resolve(catalogue, hip)


if __name__ == "__main__":
    unittest.main()
