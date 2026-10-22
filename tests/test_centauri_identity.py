"""Centauri system identities must survive every year's artwork generation."""
import csv
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import populate_sky_notes_artwork_by_date as artwork
import populate_fixed_object_artwork_by_date as fixed_artwork


class CentauriIdentityTests(unittest.TestCase):
    def test_renderer_index_contains_only_individual_hip_numbers(self):
        index = artwork.fixed_object_id_by_hip()
        self.assertTrue(all(hip.isdecimal() for hip in index))
        self.assertEqual(index['71683'], 64)
        self.assertEqual(index['70890'], 593)
        # B is retained in the system catalog, never assigned A's object identity.
        self.assertNotEqual(index.get('71681'), 64)

    def test_alpha_and_proxima_keep_distinct_renderer_identities(self):
        index = artwork.fixed_object_id_by_hip()
        metadata, _ = artwork.fixed_object_metadata()
        for fid, name, hip in ((64, 'Alpha Centauri', '71683'),
                               (593, 'Proxima Centauri', '70890')):
            with self.subTest(name=name):
                owner = fixed_artwork.owner_identity(fid, {'type': 'star', 'name': name}, index, metadata)
                self.assertEqual(owner['renderer_ref'], 'HIP ' + hip)
                self.assertEqual(owner['fixed_object_id'], fid)

    def test_component_catalog_preserves_both_bright_stars(self):
        with (ROOT / 'bright-stars-2mag.csv').open(newline='') as source:
            row = next(row for row in csv.DictReader(source) if row['proper'] == 'Alpha Centauri')
        self.assertEqual(row['hip'], '71683;71681')
        self.assertEqual(row['hd'], '128620;128621')

    def test_proxima_source_has_its_own_identity(self):
        with (ROOT / 'special-star-catalog.csv').open(newline='') as source:
            row = next(row for row in csv.DictReader(source) if row['id'] == 'proxima-centauri')
        self.assertEqual(row['hip'], '70890')
        self.assertEqual(row['con'], 'Cen')

    def test_ambiguous_and_colliding_identities_still_fail(self):
        alpha = dict(fixed_object_id=64, status='active',
                     canonical_identity=dict(namespace='hip', value='71683'),
                     identifiers=[dict(namespace='hip', value='71683;71681')])
        cases = [
            [dict(alpha, canonical_identity=dict(namespace='hip', value='70890'))],
            [dict(alpha, identifiers=[dict(namespace='hip', value='71683;bad')])],
            [alpha, dict(fixed_object_id=593, status='active',
                         identifiers=[dict(namespace='hip', value='71683')])],
        ]
        for records in cases:
            with self.subTest(records=records), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'registry.json'
                path.write_text(json.dumps(dict(fixed_objects=records)))
                with patch.object(artwork, 'FIXED_OBJECT_REGISTRY', path):
                    with self.assertRaises(RuntimeError):
                        artwork.fixed_object_id_by_hip()

    def test_centauri_specs_for_every_available_year(self):
        index = artwork.fixed_object_id_by_hip()
        metadata, _ = artwork.fixed_object_metadata()
        geometry = json.loads(artwork.GEOMETRY_REGISTRY.read_text())
        years = set()
        for source in sorted(artwork.DESCRIPTOR_ROOT.glob('*/*json')):
            for item in json.loads(source.read_text()).get('fixed_sky', []):
                fid = item.get('fixed_object_id')
                if fid not in {64, 593}:
                    continue
                with self.subTest(source=str(source), fixed_object_id=fid):
                    spec = fixed_artwork.make_spec(item, geometry, index, metadata)
                    self.assertEqual(spec['artwork_owner_identity']['fixed_object_id'], fid)
                    years.add(source.parent.name)
        self.assertTrue({'2026', '2027'} <= years)


if __name__ == '__main__':
    unittest.main()
