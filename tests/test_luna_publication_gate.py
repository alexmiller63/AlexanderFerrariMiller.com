#!/usr/bin/env python3
"""Offline regression tests for Luna's fail-closed publication decision."""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "tools/luna_publication_decision.py"
spec = importlib.util.spec_from_file_location("luna_publication_decision", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ApprovalGateTests(unittest.TestCase):
    def test_fail_closed_and_approved_and_scientific_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "generated/luna-editorial"
            base.mkdir(parents=True)
            (root / "research").mkdir()
            def write(name, value):
                (base / name).write_text(json.dumps(value), encoding="utf-8")
            write("review-queue.json", {"stories":[{"task_id":"1","title":"Alpheratz"}]})
            write("narrative-review.json", {"stories":[{"task_id":"1","hold_count":0}]})
            write("finder-svg-review.json", {"stories":[{"task_id":"1","svg_structurally_valid":True,"scientific_geometry_verified":True}]})
            write("conservative-corrections.json", {"stories":[{"task_id":"1","changes":[]}]})
            write("numeric-crosscheck.json", {"stories":[{"task_id":"1","flag_count":0}]})
            def run():
                with patch.object(module, "ROOT", root), patch.object(module, "BASE", base), contextlib.redirect_stdout(io.StringIO()):
                    module.main()
                return json.loads((base / "publication-decision.json").read_text())
            self.assertEqual(run()["ready_to_publish"], 0)
            approvals = root / "research/luna-publication-approvals.json"
            approvals.write_text(json.dumps({"1":{"editor_approved":True,"scientific_approved":True,"finder_approved":True}}))
            self.assertEqual(run()["ready_to_publish"], 1)
            self.assertTrue(run()["stories"][0]["approved"])
            write("numeric-crosscheck.json", {"stories":[{"task_id":"1","flag_count":1}]})
            self.assertEqual(run()["ready_to_publish"], 0)
            self.assertEqual(run()["published"], 0)

if __name__ == "__main__":
    unittest.main()
