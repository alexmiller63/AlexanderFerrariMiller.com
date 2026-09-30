#!/usr/bin/env python3
"""One-shot repair: fix diagnostic variable shadowing the solver's placed list.

The fast W36 Venus diagnostic introduced a local scalar named `placed` inside
search(), which made Python treat the solver's closure list `placed` as an
uninitialized local. Rename only that diagnostic scalar. No geometry, ordering,
budgets, routing, or backtracking behavior changes.
"""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

CORE = Path("tools/planet_finder_search_core.py")
text = CORE.read_text(encoding="utf-8")
old = '''                    placed = (delta["overlap"] + delta["leader_existing"] +
                              delta["route"] + delta["leader_rim"] + delta["leader_graze"])
                    summary = (
                        f"FAST W36 VENUS PROBE: generated={delta['generated']} "
                        f"viable={delta['viable']} immutable={immutable} placed={placed} "'''
new = '''                    placed_rejections = (delta["overlap"] + delta["leader_existing"] +
                                         delta["route"] + delta["leader_rim"] + delta["leader_graze"])
                    summary = (
                        f"FAST W36 VENUS PROBE: generated={delta['generated']} "
                        f"viable={delta['viable']} immutable={immutable} placed={placed_rejections} "'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: diagnostic shadow anchor count={text.count(old)}; expected 1")
CORE.write_text(text.replace(old, new, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")
print("Fixed diagnostic `placed` shadowing; solver behavior unchanged. Repair Once is now OFF.")
