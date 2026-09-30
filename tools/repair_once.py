#!/usr/bin/env python3
"""One-shot test tweak: make the fast W36 probe exercise alignment backtracking.

The existing fast probe currently stops at the first Uranus->Venus dead end,
which can occur under the initial planned alignment before recursive Mercury
alternatives are explored.  For this diagnostic only, disable that early-stop
environment flag and give exact-W36 Greek a short 30-second run.  The installed
Mercury->Venus instrumentation will then summarize distinct recursive Mercury
placements and Venus viability.  Production solver behavior is unchanged.
"""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TEST = Path("tests/test_planet_finder_ultimate_ladders.py")
text = TEST.read_text(encoding="utf-8")
old = '''def test_00_fast_w36_venus_dead_end(monkeypatch):
    """Fast diagnostic: stop at the first exact-W36 Greek Uranus->Venus dead end."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    monkeypatch.setenv("PLANET_FINDER_FAST_VENUS_PROBE", "1")
    bodies = synthetic_bodies(W36_KNOWN_GOOD)
    with pytest.raises(RuntimeError, match="FAST_W36_VENUS_PROBE_COMPLETE"):
        layout(FinderMode.GREEK, bodies, target_solutions=1,
               budget={"max_node_candidates": 2000, "max_seconds": 15.0},
               context_label="fast-W36-Venus-probe")
'''
new = '''def test_00_fast_w36_venus_dead_end(monkeypatch):
    """Fast exact-W36 Greek probe: expose recursive Mercury -> Venus behavior."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")
    monkeypatch.delenv("PLANET_FINDER_FAST_VENUS_PROBE", raising=False)
    bodies = synthetic_bodies(W36_KNOWN_GOOD)
    try:
        result = layout(FinderMode.GREEK, bodies, target_solutions=1,
                        budget={"max_node_candidates": 2000, "max_seconds": 30.0},
                        context_label="fast-W36-Mercury-Venus-probe")
    except TimeoutError:
        # Timeout is an acceptable endpoint for this diagnostic: the solver's
        # compact failure summary contains the Mercury -> Venus measurements.
        return
    assert_complete_valid_layout(result, bodies, FinderMode.GREEK)
'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: fast W36 probe anchor count={text.count(old)}; expected 1")
TEST.write_text(text.replace(old, new, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")
print("Fast W36 probe now measures recursive Mercury-to-Venus behavior. Repair Once is now OFF.")
