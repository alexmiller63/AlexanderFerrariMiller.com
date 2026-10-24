"""Exercise the real six-collection selection without making API calls."""
import copy
import json
import unittest
from tools import select_missing_story_candidates as selector
from tools.luna_story_pipeline import resolve_objects


class CuratedPreflightTests(unittest.TestCase):
    def test_complete_queue_is_curated_unique_and_supports_deep_sky(self):
        tasks = selector.candidates(1000)
        scope, unresolved = selector.curated_scope()
        ids = {int(t['id']) for t in tasks}
        self.assertEqual(len(ids), len(tasks))
        self.assertTrue(ids <= scope)
        # These figure-only stars were previously admitted by the HIP-only selector.
        self.assertTrue(ids.isdisjoint({79, 80, 81, 82, 83}))
        self.assertTrue(any(t['identity']['namespace'] == 'ngc' for t in tasks))
        self.assertEqual(set(map(int, resolve_objects(tasks).values())), ids)
        self.assertTrue(any(t['key'] == 'M24' for t in unresolved))

    def test_tampered_permanent_id_and_duplicate_tasks_rejected(self):
        task = selector.candidates(1)[0]
        bad = copy.deepcopy(task)
        bad['id'] = '999999'
        with self.assertRaises(RuntimeError):
            resolve_objects([bad])
        with self.assertRaises(RuntimeError):
            resolve_objects([task, task])

    def test_legacy_recovered_pilots_still_resolve(self):
        manifest = json.loads((selector.ROOT / 'research/luna-pilot-candidates.json').read_text())
        self.assertEqual(len(resolve_objects(manifest)), 10)


if __name__ == '__main__':
    unittest.main()
