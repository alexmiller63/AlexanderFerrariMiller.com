#!/usr/bin/env python3
"""One-shot: make deterministic work limits authoritative.

The existing max_seconds value remains a performance target for diagnostics,
but no longer truncates deterministic search/refinement. A separate generous
hard wall-clock fuse protects CI from a genuinely runaway process.
"""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search.py")
text = P.read_text(encoding="utf-8")

old = '''    budget["started"] = time.monotonic()
    diagnostic_print(f"Planet Finder {mode}: MODE CLOCK STARTED: limit={budget['max_seconds']:.1f}s", flush=True)
'''
new = '''    budget["started"] = time.monotonic()
    # Deterministic node/candidate limits decide the search.  Wall time is only
    # an emergency CI fuse, deliberately well above the performance target so
    # runner-speed variation cannot normally change PASS/FAIL.
    hard_wall_seconds = max(300.0, budget["max_seconds"] * 5.0)
    diagnostic_print(
        f"Planet Finder {mode}: MODE CLOCK STARTED: performance-target={budget['max_seconds']:.1f}s "
        f"hard-fuse={hard_wall_seconds:.1f}s",
        flush=True,
    )
'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: clock-start anchor count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''        if now - budget["started"] >= budget["max_seconds"]:
            raise RuntimeError(f"Planet Finder {mode} mode wall-clock budget exhausted (limit {budget['max_seconds']:.1f}s)")
'''
new = '''        if now - budget["started"] >= hard_wall_seconds:
            raise RuntimeError(
                f"Planet Finder {mode} emergency wall-clock fuse exhausted "
                f"(limit {hard_wall_seconds:.1f}s)"
            )
'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: controller clock anchor count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''                refinement_deadline=budget["started"] + budget["max_seconds"],
'''
new = '''                refinement_deadline=None,
'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: refinement deadline anchor count={text.count(old)}")
text = text.replace(old, new, 1)

P.write_text(text, encoding="utf-8")

me = Path(__file__)
me.write_text(me.read_text(encoding="utf-8").replace("ENABLED = True", "ENABLED = False", 1), encoding="utf-8")
print("Deterministic search limits are authoritative; wall clock is now a 5x/300s emergency fuse. Repair Once is OFF.")
