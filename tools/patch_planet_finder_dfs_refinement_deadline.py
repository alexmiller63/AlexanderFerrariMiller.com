#!/usr/bin/env python3
"""One-shot guarded patch: enforce refinement deadline inside fixed-order DFS."""
from pathlib import Path

SEARCH = Path("tools/planet_finder_search.py")
GEN = Path("tools/generate_planet_finders.py")

s = SEARCH.read_text(encoding="utf-8")
g = GEN.read_text(encoding="utf-8")

old = '''                displacement_scale=refinement_scales[refinement_index],\n                body_attempts=body_attempts,\n            )\n'''
new = '''                displacement_scale=refinement_scales[refinement_index],\n                body_attempts=body_attempts,\n                refinement_deadline=refinement_deadlines[refinement_index],\n            )\n'''
if s.count(old) != 1:
    raise SystemExit(f"search call block count={s.count(old)}; expected 1")
s = s.replace(old, new, 1)
SEARCH.write_text(s, encoding="utf-8")

old_sig = '''def _solve_order(mode: str, bodies, order, budget, target_solutions=5, order_index=1, total_orders=None, context_label=None, displacement_scale=2.0, body_attempts=None):\n'''
new_sig = '''def _solve_order(mode: str, bodies, order, budget, target_solutions=5, order_index=1, total_orders=None, context_label=None, displacement_scale=2.0, body_attempts=None, refinement_deadline=None):\n'''
if g.count(old_sig) != 1:
    raise SystemExit(f"solver signature count={g.count(old_sig)}; expected 1")
g = g.replace(old_sig, new_sig, 1)

old_search = '''        run_elapsed = time.monotonic() - budget["started"]\n        if run_elapsed >= budget["max_seconds"]:\n'''
new_search = '''        now = time.monotonic()\n        if refinement_deadline is not None and now >= refinement_deadline:\n            diagnostic_print(\n                f"Planet Finder {mode}: DFS REFINEMENT DEADLINE order={order_index} "\n                f"depth={depth}/{len(order)} body={current_body}; returning to controller",\n                flush=True,\n            )\n            return False\n        run_elapsed = now - budget["started"]\n        if run_elapsed >= budget["max_seconds"]:\n'''
if g.count(old_search) != 1:
    raise SystemExit(f"DFS clock block count={g.count(old_search)}; expected 1")
g = g.replace(old_search, new_search, 1)

old_candidate = '''            run_elapsed = time.monotonic() - budget["started"]\n            if run_elapsed >= budget["max_seconds"]:\n'''
new_candidate = '''            now = time.monotonic()\n            if refinement_deadline is not None and now >= refinement_deadline:\n                stats["blocked"] = "refinement-deadline"\n                diagnostic_print(\n                    f"Planet Finder {mode}: CANDIDATE REFINEMENT DEADLINE "\n                    f"order={order_index} depth={depth}/{len(order)} body={name}; "\n                    f"returning to controller",\n                    flush=True,\n                )\n                return\n            run_elapsed = now - budget["started"]\n            if run_elapsed >= budget["max_seconds"]:\n'''
if g.count(old_candidate) != 1:
    raise SystemExit(f"candidate clock block count={g.count(old_candidate)}; expected 1")
g = g.replace(old_candidate, new_candidate, 1)
GEN.write_text(g, encoding="utf-8")
print("patched controller call and fixed-order DFS refinement deadline")
