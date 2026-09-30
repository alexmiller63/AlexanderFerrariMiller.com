#!/usr/bin/env python3
"""One-shot repair: put the fast W36 Venus diagnostic in the existing test suite.

No workflow changes. The production solver hook is diagnostic-only and activates
only when the test sets PLANET_FINDER_FAST_VENUS_PROBE=1.
"""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

CORE = Path("tools/planet_finder_search_core.py")
text = CORE.read_text(encoding="utf-8")
hook = '''                if os.environ.get("PLANET_FINDER_FAST_VENUS_PROBE") == "1":
                    immutable = delta["immutable_reserved"] + delta["immutable_rim"]
                    placed = (delta["overlap"] + delta["leader_existing"] +
                              delta["route"] + delta["leader_rim"] + delta["leader_graze"])
                    summary = (
                        f"FAST W36 VENUS PROBE: generated={delta['generated']} "
                        f"viable={delta['viable']} immutable={immutable} placed={placed} "
                        f"detail[reserved={delta['immutable_reserved']},rim={delta['immutable_rim']},"
                        f"overlap={delta['overlap']},leader={delta['leader_existing']},"
                        f"route={delta['route']},leader-rim={delta['leader_rim']},"
                        f"graze={delta['leader_graze']}] "
                        f"uranus_box={delta['uranus_box']} uranus_path={delta['uranus_path']}"
                    )
                    print(summary, flush=True)
                    raise RuntimeError("FAST_W36_VENUS_PROBE_COMPLETE")
'''
if hook not in text:
    old = '''                uranus_venus_prefixes.append(delta)\n\n            backtracks += 1\n'''
    new = '''                uranus_venus_prefixes.append(delta)\n''' + hook + '''\n            backtracks += 1\n'''
    if text.count(old) != 1:
        raise SystemExit(f"Safety stop: probe hook anchor count={text.count(old)}; expected 1")
    CORE.write_text(text.replace(old, new, 1), encoding="utf-8")
else:
    print("Fast Venus diagnostic hook already present.")

TEST = Path("tests/test_planet_finder_ultimate_ladders.py")
test = TEST.read_text(encoding="utf-8")
marker = '''@pytest.mark.parametrize("mode", [FinderMode.GREEK, FinderMode.LATIN])\ndef test_w36_uranus_breakpoint'''
new_test = '''def test_00_fast_w36_venus_dead_end(monkeypatch):
    """Fast diagnostic: stop at the first exact-W36 Greek Uranus->Venus dead end."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0")
    monkeypatch.setenv("PLANET_FINDER_FAST_VENUS_PROBE", "1")
    bodies = synthetic_bodies(W36_KNOWN_GOOD)
    with pytest.raises(RuntimeError, match="FAST_W36_VENUS_PROBE_COMPLETE"):
        layout(FinderMode.GREEK, bodies, target_solutions=1,
               budget={"max_node_candidates": 2000, "max_seconds": 15.0},
               context_label="fast-W36-Venus-probe")


@pytest.mark.parametrize("mode", [FinderMode.GREEK, FinderMode.LATIN])
def test_w36_uranus_breakpoint'''
if "def test_00_fast_w36_venus_dead_end" not in test:
    if test.count(marker) != 1:
        raise SystemExit(f"Safety stop: existing W36 test anchor count={test.count(marker)}; expected 1")
    TEST.write_text(test.replace(marker, new_test, 1), encoding="utf-8")
else:
    print("Fast W36 Venus test already present.")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")
print("Added fast W36 Venus diagnostic to existing Planet Finder tests; no workflow changes. Repair Once is now OFF.")
