#!/usr/bin/env python3
"""One-shot diagnostic: compare 1.8 vs 1.7 Venus-Sun alignment leader paths."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")
old = '''                    if os.environ.get("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF") == "1":
                        diagnostic_print(
                            f"Planet Finder {mode}: ALIGNMENT CLIFF TRACE body={name} "
                            f"route_none={path is None} label_hit={label_hit} rim_hit={rim_hit} "
                            f"leader_graze={graze} chosen={','.join(chosen.keys())}",
                            level=1, flush=True,
                        )
'''
new = '''                    if os.environ.get("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF") == "1":
                        prior_summary = [
                            [(round(px, 1), round(py, 1)) for px, py in prior]
                            for prior in prior_paths
                        ]
                        path_summary = None if path is None else [
                            (round(px, 1), round(py, 1)) for px, py in path
                        ]
                        diagnostic_print(
                            f"Planet Finder {mode}: ALIGNMENT CLIFF TRACE body={name} "
                            f"route_none={path is None} label_hit={label_hit} rim_hit={rim_hit} "
                            f"leader_graze={graze} chosen={','.join(chosen.keys())} "
                            f"path={path_summary} prior_paths={prior_summary}",
                            level=1, flush=True,
                        )
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: alignment cliff trace block did not match exactly once")
TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")

TEST = Path("tests/test_planet_finder_w02_conjunction.py")
test = TEST.read_text(encoding="utf-8")
marker = '\n\ndef test_greek_venus_sun_separation_sweep(monkeypatch):\n'
insert = '''\n\ndef test_greek_venus_sun_1_8_vs_1_7_forensic(monkeypatch):
    """Compare the last passing and first failing ordinary-alignment cases."""
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "3")
    monkeypatch.setenv("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF", "1")

    expected_names = {name for _, name, _ in conjunction_case(2.0)}
    for separation in (1.8, 1.7):
        bodies = conjunction_case(separation)
        print(f"ALIGNMENT CLIFF CASE START separation={separation:.1f}deg", flush=True)
        started = time.monotonic()
        result = layout(
            FinderMode.GREEK,
            bodies,
            target_solutions=1,
            budget={"max_node_candidates": 2000, "max_seconds": 15.0},
            context_label=f"venus-sun-{separation:.1f}deg-forensic",
        )
        elapsed = time.monotonic() - started
        actual = [name for _, name, _, _, _ in result]
        print(
            f"ALIGNMENT CLIFF CASE RESULT separation={separation:.1f}deg "
            f"elapsed={elapsed:.3f}s placed={len(actual)}/{len(expected_names)} order={actual}",
            flush=True,
        )
        if separation == 1.8:
            assert set(actual) == expected_names
        else:
            assert set(actual) != expected_names, "1.7deg unexpectedly passed; cliff moved"
'''
if test.count(marker) != 1:
    raise SystemExit("Safety stop: sweep test insertion marker did not match exactly once")
TEST.write_text(test.replace(marker, insert + marker, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Added diagnostic-only 1.8-vs-1.7 leader-path comparison. "
    "No geometry, thresholds, candidate ordering, or acceptance behavior changed. Repair Once is now OFF."
)
