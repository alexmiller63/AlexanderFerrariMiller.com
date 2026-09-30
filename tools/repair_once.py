#!/usr/bin/env python3
"""One-shot: isolate W01 Greek real-five-plus-wide-wrap with compact diagnostics.

Test-harness change only. Solver code, geometry, candidate ordering, and budgets
are untouched. Self-disables after running.
"""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TEST = Path("tests/test_planet_finder_ultimate_ladders.py")
text = TEST.read_text(encoding="utf-8")

old = '''@pytest.mark.parametrize("mode", MODES)
def test_ultimate_w01_ladder(monkeypatch, mode):
    run_existing_ladder(monkeypatch, "W01", mode, W01_LADDER)
'''
new = '''def test_ultimate_w01_ladder(monkeypatch):
    """Diagnostic isolation: W01 Greek real-five-plus-wide-wrap only."""
    level, longitudes = next(
        item for item in W01_LADDER if item[0] == "real-five-plus-wide-wrap"
    )
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "2")
    bodies = synthetic_bodies(longitudes)
    print("W01 GREEK SINGLE-RUNG START level=real-five-plus-wide-wrap budget=60s", flush=True)
    result = layout(
        FinderMode.GREEK,
        bodies,
        target_solutions=1,
        budget={"max_node_candidates": 2000, "max_seconds": REGRESSION_SECONDS},
        context_label="ultimate-W01-real-five-plus-wide-wrap-greek",
    )
    assert_complete_valid_layout(result, bodies, FinderMode.GREEK)
    print("W01 GREEK SINGLE-RUNG PASS level=real-five-plus-wide-wrap", flush=True)
'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: W01 test anchor count={text.count(old)}")
TEST.write_text(text.replace(old, new, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
self_text = self_text.replace("ENABLED = True", "ENABLED = False", 1)
me.write_text(self_text, encoding="utf-8")

print("Isolated W01 Greek real-five-plus-wide-wrap at diagnostic level 2. Solver unchanged. Repair Once is now OFF.")
