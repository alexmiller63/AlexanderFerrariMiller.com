#!/usr/bin/env python3
"""One-shot repair: let a capped planned alignment fall back to recursive alignment.

A planned alignment is only a fast first attempt. If ordinary DFS hits its
per-body safety cap under that preplacement, the cap currently escapes before
_search_alignment_fallback can restore the planned geometry and retry the
alignment recursively. Preserve the cap signal only if the recursive alignment
layer also hits it. No geometry, ordering, routing, or candidate rules change.
"""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

CORE = Path("tools/planet_finder_search_core.py")
text = CORE.read_text(encoding="utf-8")
old = '''    if preplacement:\n        if search(0):\n            return True\n        planned, _ = preplacement\n        for group in groups:\n            for original_index, _ in group:\n                staged.pop(original_index)\n        del placed[-len(planned):]\n        del leaders[-len(planned):]\n        del leader_names[-len(planned):]\n        diagnostic_print("Planet Finder: ALIGNMENT PREPLACEMENT BLOCKED; "\n                         "retrying recursive alignment layer", flush=True)\n'''
new = '''    if preplacement:\n        capped_preplacement = None\n        try:\n            if search(0):\n                return True\n        except DepthNodeBudgetExhausted as exc:\n            # A cap reached under the planner's first complete alignment is\n            # evidence that this preplacement is a dead/expensive branch, not\n            # proof that the alignment layer itself is exhausted. Restore it\n            # and let recursive alignment backtracking try sibling placements.\n            capped_preplacement = exc\n        planned, _ = preplacement\n        for group in groups:\n            for original_index, _ in group:\n                staged.pop(original_index)\n        del placed[-len(planned):]\n        del leaders[-len(planned):]\n        del leader_names[-len(planned):]\n        diagnostic_print(\n            "Planet Finder: ALIGNMENT PREPLACEMENT "\n            + (\n                f"CAPPED body={capped_preplacement.name}; "\n                if capped_preplacement is not None else "BLOCKED; "\n            )\n            + "retrying recursive alignment layer",\n            flush=True,\n        )\n'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: alignment fallback anchor count={text.count(old)}; expected 1")
CORE.write_text(text.replace(old, new, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")
print("Planned-alignment caps now restore and retry recursive alignment. Repair Once is now OFF.")
