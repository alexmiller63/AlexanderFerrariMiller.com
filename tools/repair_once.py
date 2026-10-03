#!/usr/bin/env python3
"""One-shot forensic: bypass the legacy alignment preplanner."""

from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")

old = '''        alignment_preplacement = plan_alignment_layer()
        diagnostic_print(
            f"Planet Finder {mode}: PRE-DFS TIMING alignment-plan END "
            f"elapsed={time.monotonic() - phase_started:.3f}s "
            f"result={'success' if alignment_preplacement is not None else 'none'}",
            level=1, flush=True,
        )
'''
new = '''        # Forensic experiment: bypass the legacy exhaustive alignment
        # preplanner and give the full clock to the recursive alignment solver.
        # Keep plan_alignment_layer() intact so this is trivially reversible.
        alignment_preplacement = None
        diagnostic_print(
            f"Planet Finder {mode}: PRE-DFS TIMING alignment-plan END "
            f"elapsed={time.monotonic() - phase_started:.3f}s "
            f"result=bypassed-forensic",
            level=1, flush=True,
        )
'''

if text.count(old) != 1:
    raise SystemExit("Safety stop: alignment preplanner call missing or non-unique")
P.write_text(text.replace(old, new, 1), encoding="utf-8")

me = Path(__file__)
source = me.read_text(encoding="utf-8")
needle = "\nENABLED = True\n"
if source.count(needle) != 1:
    raise SystemExit("Safety stop: ENABLED assignment not unique")
me.write_text(source.replace(needle, "\nENABLED = False\n", 1), encoding="utf-8")
print("Bypassed legacy alignment preplanner for forensic test; Repair Once is OFF.")
