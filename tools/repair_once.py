#!/usr/bin/env python3
"""One-shot diagnostic: identify Ceres blockers inside Mixed JSM 25%.

Adds a focused test only; production Planet Finder code is unchanged.
Repair Once self-disables after installing the diagnostic.
"""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TEST = Path("tests/test_planet_finder_ultimate_ladders.py")
test = TEST.read_text(encoding="utf-8")
anchor = '''def test_w36_mixed_jsm_breakpoint(monkeypatch):
    run_ladder(monkeypatch, "W36-MIXED-JSM", FinderMode.MIXED,
               W36_MIXED_JSM_LADDER, stop_on_failure=False)
'''
addition = anchor + '''\n\ndef test_02_w36_mixed_jsm_zero_vs_25_forensic(monkeypatch):
    """Compare the passing 0% JSM state directly with the failing 25% state."""
    enable_alignment_fix(monkeypatch)
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "4")
    for level, fraction in (("jsm-0pct", 0.0), ("jsm-25pct", 0.25)):
        longitudes, expected_groups = jsm_case(fraction)
        print(f"JSM FORENSIC {level} LONGITUDES " +
              " ".join(f"{name}={lon:.6f}" for name, lon in longitudes.items()), flush=True)
        bodies = synthetic_bodies(longitudes)
        actual_groups = group_names(bodies)
        print(f"JSM FORENSIC {level} GROUPS={actual_groups}", flush=True)
        assert actual_groups == sorted(expected_groups)
        try:
            result = layout(
                FinderMode.MIXED, bodies, target_solutions=1,
                budget={"max_node_candidates": 2000, "max_seconds": 15.0},
                context_label=f"forensic-W36-{level}-mixed",
            )
            assert_complete_valid_layout(result, bodies, FinderMode.MIXED)
        except Exception as exc:
            print(f"JSM FORENSIC {level} RESULT=FAIL {type(exc).__name__}: {exc}", flush=True)
        else:
            print(f"JSM FORENSIC {level} RESULT=PASS", flush=True)
'''
if test.count(anchor) != 1:
    raise SystemExit(f"Safety stop: JSM test anchor count={test.count(anchor)}; expected 1")
TEST.write_text(test.replace(anchor, addition, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print("Raised focused JSM forensic diagnostics to blocker-identity level 4. Production code unchanged. Repair Once is now OFF.")
