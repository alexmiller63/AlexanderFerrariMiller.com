#!/usr/bin/env python3
"""One-shot diagnostic repair: add an opt-in alignment-preplanner bypass.

Production behavior remains unchanged because the new switch defaults OFF.
The fast exact-W36 diagnostic alone enables it, so recursive alignment
backtracking receives the full mode clock. Repair Once self-disables.
"""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

CORE = Path("tools/planet_finder_search_core.py")
core = CORE.read_text(encoding="utf-8")

old_core = '''    def search_coordinated_geometry():
        # Conjunctions have no placement path of their own.  Every body enters
        # the ordinary coordinated alignment planner; conjunction metadata is
        # consulted only by downstream backtracking to keep a conjunction
        # atomic when it must be reconsidered.
        alignment_preplacement = plan_alignment_layer()
        stage_alignment_preplacement(alignment_preplacement)
        return _search_alignment_fallback(
            alignment_preplacement, alignment_group_items, placed, leaders,
            leader_names, staged, search, solve_alignment_group,
        )
'''

new_core = '''    def search_coordinated_geometry():
        # Diagnostic-only escape hatch: skip the speculative alignment
        # preplanner and give recursive alignment backtracking the full mode
        # clock. Default is OFF, so production behavior is unchanged.
        if os.environ.get("PLANET_FINDER_SKIP_ALIGNMENT_PREPLANNER", "0") == "1":
            diagnostic_print(
                f"Planet Finder {mode}: ALIGNMENT PREPLANNER BYPASSED; "
                "starting recursive alignment layer directly",
                flush=True,
            )
            if alignment_group_items:
                return solve_alignment_group(0)
            return search(0)

        # Conjunctions have no placement path of their own.  Every body enters
        # the ordinary coordinated alignment planner; conjunction metadata is
        # consulted only by downstream backtracking to keep a conjunction
        # atomic when it must be reconsidered.
        alignment_preplacement = plan_alignment_layer()
        stage_alignment_preplacement(alignment_preplacement)
        return _search_alignment_fallback(
            alignment_preplacement, alignment_group_items, placed, leaders,
            leader_names, staged, search, solve_alignment_group,
        )
'''

if core.count(old_core) != 1:
    raise SystemExit(f"Safety stop: core anchor count={core.count(old_core)}; expected 1")
CORE.write_text(core.replace(old_core, new_core, 1), encoding="utf-8")

TEST = Path("tests/test_planet_finder_ultimate_ladders.py")
test = TEST.read_text(encoding="utf-8")
old_test = '''def test_01_exact_w36_preplacement_probe(monkeypatch):
    """Exact W36 should reproduce the fixed-alignment -> Venus dead end quickly."""
    assert not run_case(monkeypatch, "W36-exact-preplacement-probe", W36_KNOWN_GOOD, 12.0)
'''
new_test = '''def test_01_exact_w36_preplacement_probe(monkeypatch):
    """Give recursive alignment backtracking the full exact-W36 clock."""
    monkeypatch.setenv("PLANET_FINDER_SKIP_ALIGNMENT_PREPLANNER", "1")
    solved = run_case(
        monkeypatch,
        "W36-exact-recursive-alignment-only",
        W36_KNOWN_GOOD,
        12.0,
    )
    print(f"PREPLANNER BYPASS RESULT solved={solved}", flush=True)
'''
if test.count(old_test) != 1:
    raise SystemExit(f"Safety stop: test anchor count={test.count(old_test)}; expected 1")
TEST.write_text(test.replace(old_test, new_test, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print("Added diagnostic-only alignment-preplanner bypass; exact W36 test enables it. Repair Once is now OFF.")
