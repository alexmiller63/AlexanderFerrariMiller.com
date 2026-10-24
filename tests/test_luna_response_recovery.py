"""Offline response/restart regressions; all external boundaries are replaced."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import luna_story_pipeline as p


def response(text='Complete story.', status='completed', reason=None):
    return json.dumps({'status': status, 'output_text': text,
                       'incomplete_details': {'reason': reason} if reason else None,
                       'usage': {'input_tokens': 10, 'output_tokens': 20}})


class ResponseRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / 'generated/luna-pilot'
        self.out.mkdir(parents=True)
        self.ledger = {'estimated_usd': 0., 'calls': []}
        self.ledger_path = self.out / 'ledger.json'
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(p, 'ROOT', self.root))
        self.stack.enter_context(patch.object(p, 'OUT', self.out))
        self.persisted = []
        self.stack.enter_context(patch.object(p, 'persist_checkpoint',
            side_effect=lambda path, ledger: self.persisted.append(path.name)))
        self.stack.enter_context(patch.object(p.time, 'sleep'))
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))

    def ask(self):
        return p.paid_story_response('1:draft', 'instruction', 'source', 'test-model',
                                    'test-secret', .1, .5, self.ledger, self.ledger_path)

    def test_empty_then_incomplete_then_complete_accounted_and_saved(self):
        with patch.object(p, 'request_json', side_effect=[response(''),
                response('partial', 'incomplete', 'max_output_tokens'), response('Whole story.')]) as api:
            self.assertEqual(self.ask(), 'Whole story.')
        self.assertEqual([c.args[1]['max_output_tokens'] for c in api.call_args_list], [4000, 4000, 8000])
        self.assertEqual(len(self.ledger['calls']), 3)
        self.assertEqual(len(self.persisted), 3)
        self.assertEqual(len(list(self.out.glob('*.response.json'))), 3)
        self.assertAlmostEqual(self.ledger['estimated_usd'], 3 * .000011)

    def test_persistent_incomplete_is_not_accepted(self):
        with patch.object(p, 'request_json', return_value=response('partial', 'incomplete', 'max_output_tokens')) as api:
            with self.assertRaises(p.StoryResponseError):
                self.ask()
        self.assertEqual(api.call_count, 3)
        self.assertEqual(len(self.ledger['calls']), 3)

    def test_malformed_response_is_saved_and_retried(self):
        with patch.object(p, 'request_json', side_effect=['[]', 'not json', response('Recovered')]):
            self.assertEqual(self.ask(), 'Recovered')
        self.assertEqual(len(self.persisted), 3)
        self.assertEqual(len(self.ledger['calls']), 3)

    def test_budget_stops_before_retry(self):
        self.ledger['estimated_usd'] = p.CAP - .004
        with patch.object(p, 'request_json', return_value=response('', 'incomplete', 'max_output_tokens')) as api:
            with self.assertRaises(p.BudgetExceeded):
                self.ask()
        self.assertEqual(api.call_count, 1)

    def test_authentication_stops_without_retry(self):
        with patch.object(p, 'request_json', side_effect=p.APIRequestError('Unauthorized', 401, 'invalid_api_key')) as api:
            with self.assertRaises(p.APIRequestError):
                self.ask()
        self.assertEqual(api.call_count, 1)
        self.assertEqual(len(self.persisted), 1)

    def test_timeout_and_rate_limit_retry_with_conservative_accounting(self):
        with patch.object(p, 'request_json', side_effect=[TimeoutError('timeout'),
                p.APIRequestError('slow down', 429, 'rate_limit_exceeded'), response('Recovered')]):
            self.assertEqual(self.ask(), 'Recovered')
        self.assertEqual(len(self.ledger['calls']), 3)
        self.assertGreater(self.ledger['estimated_usd'], .006)

    def test_main_skips_failed_object_completes_next_and_restart_is_free(self):
        tasks = [{'id': str(i), 'title': f'Star {i}', 'sources': ['https://example.org/source']} for i in (1, 2)]
        (self.root / 'manifest.json').write_text(json.dumps(tasks))
        self.ledger_path.write_text(json.dumps(self.ledger))
        # Avoid source network: simulate already persisted evidence, as in a restart.
        for i in (1, 2):
            (self.out / f'{i}.evidence.json').write_text(json.dumps([
                {'url': 'https://example.org/source', 'excerpt': 'Observed source evidence. ' * 20}]))
        good = '# Star 2\n' + ('word ' * 470) + 'https://example.org/source'
        argv = ['pipeline', '--manifest', 'manifest.json', '--model', 'test',
                '--input-price', '.1', '--output-price', '.5', '--execute']
        with patch.object(p, 'resolve_objects', return_value={'1': '1', '2': '2'}), \
             patch.dict('os.environ', {'OPENAI_API_KEY': 'test-secret'}), patch('sys.argv', argv), \
             patch.object(p, 'request_json', side_effect=[response('')] * 3 + [response(good)]) as api:
            p.main()
        self.assertEqual(api.call_count, 4)
        self.assertTrue((self.out / '1.failure.json').exists())
        self.assertFalse((self.out / '1.md').exists())
        for suffix in ('md', 'audit.txt', 'research.txt', 'gate.json'):
            self.assertIn(f'2.{suffix}', self.persisted)
        self.assertFalse(json.loads((self.out / '2.gate.json').read_text())['publication_approved'])
        # Simulate interruption after paid stage saved, before final bundle was written.
        (self.out / '2.md').unlink()
        (self.root / 'manifest.json').write_text(json.dumps(tasks[1:]))
        with patch.object(p, 'resolve_objects', return_value={'2': '2'}), \
             patch.dict('os.environ', {'OPENAI_API_KEY': 'test-secret'}), patch('sys.argv', argv), \
             patch.object(p, 'request_json', side_effect=AssertionError('Paid call repeated')):
            p.main()
        self.assertEqual((self.out / '2.md').read_text().strip(), good.strip())
        self.assertEqual(len(json.loads(self.ledger_path.read_text())['calls']), 4)


if __name__ == '__main__':
    unittest.main()
