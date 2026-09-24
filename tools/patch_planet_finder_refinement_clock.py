#!/usr/bin/env python3
"""One-shot source patcher: reserve mode-clock time for every refinement."""

from pathlib import Path

PATH = Path("tools/planet_finder_search.py")
text = PATH.read_text(encoding="utf-8")

old = '''    refinement_scales = (2.0, 1.5, 1.0, 0.5, 0.25)\n    refinement_index = 0\n    attempted_orders = set()\n'''
new = '''    refinement_scales = (2.0, 1.5, 1.0, 0.5, 0.25)\n    refinement_index = 0\n    # Keep one wall clock per notation mode, but reserve an equal cumulative\n    # share for each refinement so a coarse geometry cannot consume time that\n    # belongs to the finer fallback geometries.\n    refinement_deadlines = tuple(\n        budget["started"] + budget["max_seconds"] * (i + 1) / len(refinement_scales)\n        for i in range(len(refinement_scales))\n    )\n    attempted_orders = set()\n'''
if text.count(old) != 1:
    raise SystemExit(f"expected exactly one refinement initialization block, found {text.count(old)}")
text = text.replace(old, new, 1)

old = '''    while state != "SCORE":\n        if time.monotonic() - budget["started"] >= budget["max_seconds"]:\n            raise RuntimeError(\n                f"Planet Finder {mode} mode wall-clock budget exhausted "\n                f"(limit {budget['max_seconds']:.1f}s)"\n            )\n\n        if state == "REFINE":\n'''
new = '''    while state != "SCORE":\n        now = time.monotonic()\n        if now - budget["started"] >= budget["max_seconds"]:\n            raise RuntimeError(\n                f"Planet Finder {mode} mode wall-clock budget exhausted "\n                f"(limit {budget['max_seconds']:.1f}s)"\n            )\n        if now >= refinement_deadlines[refinement_index]:\n            if refinement_index + 1 >= len(refinement_scales):\n                raise RuntimeError(\n                    f"Planet Finder {mode} mode wall-clock budget exhausted "\n                    f"(limit {budget['max_seconds']:.1f}s)"\n                )\n            diagnostic_print(\n                f"Planet Finder {mode}: REFINEMENT TIME SLICE EXHAUSTED "\n                f"at {refinement_scales[refinement_index]:g} label-lengths; "\n                f"elapsed={now - budget['started']:.1f}s; advancing",\n                flush=True,\n            )\n            state = "REFINE"\n            continue\n\n        if state == "REFINE":\n'''
if text.count(old) != 1:
    raise SystemExit(f"expected exactly one controller clock block, found {text.count(old)}")
text = text.replace(old, new, 1)

PATH.write_text(text, encoding="utf-8")
print(f"patched {PATH}: cumulative refinement deadlines installed")
