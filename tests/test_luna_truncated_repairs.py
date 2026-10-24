"""Offline selection and execution tests for token-limited story repair."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import luna_story_pipeline as pipeline
from tools import select_truncated_story_repairs as selector


class TruncatedRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / 'generated/luna-pilot'
        self.out.mkdir(parents=True)
        (self.root / 'database').mkdir()
        objects = [{'fixed_object_id': i, 'source_records': [{'facts': {'name': f'Star {i}'}}]} for i in range(1, 6)]
        registry = [{'fixed_object_id': i, 'status': 'active', 'identifiers': [{'namespace': 'ngc', 'value': str(i)}]} for i in range(1, 6)]
        (self.root / 'database/fixed-objects.json').write_text(json.dumps({'fixed_objects': objects}))
        (self.root / 'database/fixed-object-registry.json').write_text(json.dumps({'fixed_objects': registry}))
        for i in range(1, 6):
            (self.out / f'{i}.evidence.json').write_text(json.dumps([
                {'url': f'https://simbad.cds.unistra.fr/simbad/sim-id?Ident=NGC%20{i}', 'excerpt': 'Original observations. ' * 30}]))

    def record(self, ident, text, status='incomplete', final=True):
        response = {'status': status, 'output_text': text,
                    'incomplete_details': {'reason': 'max_output_tokens'}}
        (self.out / f'{ident}.draft.attempt.response.json').write_text(json.dumps({
            'stage': f'{ident}:draft', 'response_body': json.dumps(response)}))
        if final:
            (self.out / f'{ident}.md').write_text(text)

    def test_select_only_final_cutoffs_and_empty_interrupted_work(self):
        self.record(1, 'cut off')
        self.record(2, 'earlier cut off')
        (self.out / '2.md').write_text('Successfully corrected later.')
        self.record(3, '', final=False)
        self.record(4, 'Complete.', status='completed')
        self.record(5, 'cut off')
        (self.out / 'repairs').mkdir()
        (self.out / 'repairs/5.md').write_text('Repaired.')
        tasks, report = selector.select_repairs(self.root)
        self.assertEqual([t['id'] for t in tasks], ['1', '3'])
        self.assertEqual([r['original_draft_exists'] for r in report], [True, False])
        self.assertEqual([t['id'] for t in selector.select_repairs(self.root, limit=1)[0]], ['1'])

    def test_evidence_mismatch_stops_before_paid_calls(self):
        self.record(1, 'cut off')
        (self.out / '1.evidence.json').write_text('[{"url":"https://wrong.org"}]')
        with self.assertRaisesRegex(RuntimeError, 'does not match permanent identity'):
            selector.select_repairs(self.root)

    def test_repair_preserves_originals_shared_budget_and_free_restart(self):
        self.record(1, 'cut off')
        (self.out / '1.draft.stage.txt').write_text('cut off')
        tasks, _ = selector.select_repairs(self.root)
        original = {f.name: f.read_bytes() for f in self.out.iterdir()}
        (self.root / 'manifest.json').write_text(json.dumps(tasks))
        ledger_path = self.out / 'ledger.json'
        ledger_path.write_text(json.dumps({'estimated_usd': .21, 'calls': []}))
        good = '# Star 1\n' + 'word ' * 470 + tasks[0]['sources'][0]
        reply = json.dumps({'status': 'completed', 'output_text': good,
                            'usage': {'input_tokens': 10, 'output_tokens': 20}})
        args = ['pipeline', '--manifest', 'manifest.json', '--model', 'test',
                '--input-price', '.1', '--output-price', '.5', '--execute', '--repair-truncated']
        with patch.object(pipeline, 'ROOT', self.root), patch.object(pipeline, 'OUT', self.out), \
             patch.object(pipeline, 'resolve_objects', return_value={'1': '1'}), \
             patch.object(pipeline, 'persist_checkpoint'), patch.dict('os.environ', {'OPENAI_API_KEY': 'test-secret'}), \
             patch('sys.argv', args), contextlib.redirect_stdout(io.StringIO()):
            with patch.object(pipeline, 'request_json', return_value=reply) as api:
                pipeline.main()
            self.assertEqual(api.call_count, 1)  # Original evidence reused; no source request.
            repaired = self.out / 'repairs/1.md'
            self.assertEqual(repaired.read_text().strip(), good.strip())
            self.assertFalse((self.out / 'repairs/ledger.json').exists())
            self.assertGreater(json.loads(ledger_path.read_text())['estimated_usd'], .21)
            self.assertFalse(json.loads((self.out / 'repairs/1.gate.json').read_text())['publication_approved'])
            repaired.unlink()  # Restart after paid-stage checkpoint, before final output.
            with patch.object(pipeline, 'request_json', side_effect=AssertionError('Repeated paid call')):
                pipeline.main()
            self.assertEqual(repaired.read_text().strip(), good.strip())
        for name, content in original.items():
            self.assertEqual((self.out / name).read_bytes(), content)
        self.assertEqual(len(json.loads(ledger_path.read_text())['calls']), 1)


if __name__ == '__main__':
    unittest.main()
