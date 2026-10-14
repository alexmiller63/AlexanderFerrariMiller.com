#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools/luna_stage_approved.py"

class StageTests(unittest.TestCase):
    def test_dry_run_and_write_preserves_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "generated/luna-editorial"
            source = base / "stories/alpha-stars/77.md"
            source.parent.mkdir(parents=True)
            source.write_text("---\nfixed_object_id: 77\nstatus: pending\n---\n# Story\n")
            (base / "publication-decision.json").write_text(json.dumps({"stories":[{"task_id":"1","approved":True,"blockers":[]},{"task_id":"2","approved":False,"blockers":["not approved"]}]}))
            (base / "review-queue.json").write_text(json.dumps({"stories":[{"task_id":"1","fixed_object_id":77,"prepared_path":"generated/luna-editorial/stories/alpha-stars/77.md"},{"task_id":"2","fixed_object_id":78,"prepared_path":"generated/luna-editorial/stories/alpha-stars/78.md"}]}))
            script = SCRIPT.read_text().replace('ROOT = Path(__file__).resolve().parents[1]', 'ROOT = Path('+repr(str(root))+')')
            local = root / "stage.py"
            local.write_text(script)
            target = root / "stories/alpha-stars/77.md"
            def run(*args):
                return json.loads(subprocess.check_output([sys.executable,str(local),*args],text=True))
            self.assertEqual(run()["staged"][0]["status"],"would stage pending")
            self.assertFalse(target.exists())
            self.assertEqual(run("--write")["staged"][0]["status"],"staged pending")
            self.assertTrue(target.exists())
            target.write_text("existing editorial manuscript")
            self.assertEqual(run("--write")["staged"][0]["status"],"existing story preserved")
            self.assertEqual(target.read_text(),"existing editorial manuscript")

if __name__ == "__main__":
    unittest.main()
