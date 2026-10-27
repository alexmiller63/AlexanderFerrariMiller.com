"""Exercise the worker's actual Python request block and timezone database."""
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import pytest
import generate_planet_finder_at_instant as generator

WORKER = Path(__file__).resolve().parents[1] / 'star-almanack/js/ephemera-worker.js'


def execute_request(monkeypatch, request, generate):
    code = re.search(r'const payload = await python.runPythonAsync\(`(.*?)`\);', WORKER.read_text(), re.S).group(1)
    tree = ast.parse(code)
    tail = tree.body.pop()
    monkeypatch.setattr(generator, 'generate', generate)
    scope = {'request_json': json.dumps(request), 'json': json, 'engine': object()}
    exec(compile(tree, str(WORKER), 'exec'), scope)
    return json.loads(eval(compile(ast.Expression(tail.value), str(WORKER), 'eval'), scope))


@pytest.mark.parametrize('instant,zone,expected', [
    ('1963-10-09T12:00:00Z', 'America/New_York', 'October 9, 1963 · 8:00 AM EDT'),
    ('1963-01-09T13:00:00Z', 'America/New_York', 'January 9, 1963 · 8:00 AM EST'),
    ('1945-07-01T15:00:00Z', 'America/Los_Angeles', 'July 1, 1945 · 8:00 AM PWT'),
    ('1990-01-16T22:28:00Z', 'America/Los_Angeles', 'January 16, 1990 · 2:28 PM PST'),
    ('2026-07-01T02:30:00Z', 'Asia/Kolkata', 'July 1, 2026 · 8:00 AM IST'),
    ('2026-06-30T12:15:00Z', 'Pacific/Auckland', 'July 1, 2026 · 12:15 AM NZST'),
])
def test_historical_local_title(monkeypatch, instant, zone, expected):
    result = execute_request(monkeypatch, {'instant_utc': instant, 'timezone': zone, 'city': 'Selected city', 'mode': 'greek'}, lambda *args: '<svg/>')
    assert result['local_title'] == expected + ' · Selected city'
    assert set(result['charts']) == {'greek'}


@pytest.mark.parametrize('mode,expected', [('all', ['greek', 'latin', 'mixed']), ('greek', ['greek']), ('latin', ['latin']), ('mixed', ['mixed'])])
def test_requested_modes_preserve_exact_instant(monkeypatch, mode, expected):
    calls = []
    def render(instant, mode, engine):
        calls.append((instant, mode))
        return '<svg>' + mode + '</svg>'
    result = execute_request(monkeypatch, {'instant_utc': '1963-10-09T12:00:00Z', 'mode': mode}, render)
    assert [mode for _, mode in calls] == expected
    assert all(instant == datetime(1963, 10, 9, 12, tzinfo=timezone.utc) for instant, _ in calls)
    assert list(result['charts']) == expected


def test_all_failure_propagates_without_partial_payload(monkeypatch):
    def render(instant, mode, engine):
        if mode == 'latin':
            raise RuntimeError('layout failed')
        return '<svg/>'
    with pytest.raises(RuntimeError, match='layout failed'):
        execute_request(monkeypatch, {'instant_utc': '1963-10-09T12:00:00Z', 'mode': 'all'}, render)
