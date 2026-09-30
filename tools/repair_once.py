#!/usr/bin/env python3
"""One-shot diagnostic repair: reuse ordinary forward check after Mercury alignment.

The experiment is opt-in via PLANET_FINDER_ALIGNMENT_FORWARD_CHECK=1, so normal
production behavior remains unchanged. Repair Once self-disables.
"""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

CORE = Path("tools/planet_finder_search_core.py")
core = CORE.read_text(encoding="utf-8")

old_core = '''            try:
                solved = solve_alignment_members(group_index, next_remaining)
            finally:
'''
new_core = '''            try:
                # Diagnostic experiment: alignment members normally bypass the
                # ordinary DFS forward checker.  Once Mercury (the final member
                # of W36's final alignment group) is staged, reuse that exact
                # checker against the ordinary-body order before descending.
                # This is look-ahead pruning only; it does not choose or freeze
                # any ordinary-body placement.
                if (
                    name == "Mercury"
                    and os.environ.get("PLANET_FINDER_ALIGNMENT_FORWARD_CHECK", "0") == "1"
                    and not forward_check(0)
                ):
                    solved = False
                else:
                    solved = solve_alignment_members(group_index, next_remaining)
            finally:
'''
if core.count(old_core) != 1:
    raise SystemExit(f"Safety stop: alignment recursion anchor count={core.count(old_core)}; expected 1")
CORE.write_text(core.replace(old_core, new_core, 1), encoding="utf-8")

TEST = Path("tests/test_planet_finder_ultimate_ladders.py")
test = TEST.read_text(encoding="utf-8")
old_test = '''def test_01_exact_w36_preplacement_probe(monkeypatch):
    """Give recursive alignment backtracking the full exact-W36 clock."""
    monkeypatch.setenv("PLANET_FINDER_SKIP_ALIGNMENT_PREPLANNER", "1")
    solved = run_case(
'''
new_test = '''def test_01_exact_w36_preplacement_probe(monkeypatch):
    """Give recursive alignment backtracking the full clock plus shared forward check."""
    monkeypatch.setenv("PLANET_FINDER_SKIP_ALIGNMENT_PREPLANNER", "1")
    monkeypatch.setenv("PLANET_FINDER_ALIGNMENT_FORWARD_CHECK", "1")
    solved = run_case(
'''
if test.count(old_test) != 1:
    raise SystemExit(f"Safety stop: W36 test anchor count={test.count(old_test)}; expected 1")
TEST.write_text(test.replace(old_test, new_test, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print("Added opt-in alignment reuse of existing forward_check after Mercury. Repair Once is now OFF.")
