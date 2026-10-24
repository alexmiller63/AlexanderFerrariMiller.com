"""Regression tests for interrupted story selection; no API calls."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import select_missing_story_candidates as selector


class CandidateSelectionTests(unittest.TestCase):
    def test_interrupted_artifacts_are_not_reselected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "database").mkdir()
            (root / "generated/luna-pilot").mkdir(parents=True)
            (root / "stories").mkdir()
            objects = []
            for ident in range(1, 12):
                objects.append({"fixed_object_id": ident, "source_records": [
                    {"source_key": f"HIP {10000 + ident}", "facts": {"name": f"Star {ident}"}}]})
            (root / "database/fixed-objects.json").write_text(json.dumps({"fixed_objects": objects}))
            for suffix in ("evidence.json", "research.txt", "audit.txt", "draft.stage.txt", "correction.stage.txt", "reaudit.stage.txt", "md"):
                (root / "generated/luna-pilot" / f"{len(list((root / 'generated/luna-pilot').iterdir())) + 1}.{suffix}").write_text("checkpoint")
            with patch.object(selector, "ROOT", root):
                result = selector.candidates(10)
            self.assertEqual([int(t["id"]) for t in result], [8, 9, 10, 11])


if __name__ == "__main__":
    unittest.main()
