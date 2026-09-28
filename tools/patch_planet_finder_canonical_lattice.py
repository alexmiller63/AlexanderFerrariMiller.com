#!/usr/bin/env python3
"""Repair-once: add diagnostic-only viable candidate uniqueness accounting."""
from pathlib import Path

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old_init = '''    diagnostic_stats = {}\n    route_diagnostics = {}\n'''
new_init = '''    diagnostic_stats = {}\n    route_diagnostics = {}\n    # Diagnostic only: distinguish genuinely different admitted geometries\n    # from repeated/equivalent viable candidates.  This never filters or\n    # reorders candidates and therefore cannot change search behavior.\n    viable_geometry_seen = {}\n'''
if text.count(old_init) != 1:
    raise SystemExit(f"Safety stop: diagnostic init block count={text.count(old_init)}; expected 1")
text = text.replace(old_init, new_init, 1)

old_admit = '''            # This is the single cap point: only a fully viable candidate\n            # admitted to DFS consumes the body's candidate budget.\n            body_candidates += 1\n            if consume_body_budget:\n                body_attempts[name] += 1\n'''
new_admit = '''            # Diagnostic-only geometry signature.  Round below rendering\n            # precision so numerically insignificant float noise does not make\n            # equivalent candidates appear distinct.  Include the routed leader\n            # because the same label box with a different route is a materially\n            # different search choice.\n            geometry_signature = (\n                round(box.x, 6), round(box.y, 6),\n                round(box.w, 6), round(box.h, 6),\n                tuple((round(px, 6), round(py, 6)) for px, py in path),\n            )\n            seen = viable_geometry_seen.setdefault(name, set())\n            seen.add(geometry_signature)\n\n            # This is the single cap point: only a fully viable candidate\n            # admitted to DFS consumes the body's candidate budget.\n            body_candidates += 1\n            if consume_body_budget:\n                body_attempts[name] += 1\n'''
if text.count(old_admit) != 1:
    raise SystemExit(f"Safety stop: viable admission block count={text.count(old_admit)}; expected 1")
text = text.replace(old_admit, new_admit, 1)

old_cap = '''                    f"viable={body_attempts[name]:,}/{budget['max_node_candidates']:,} "\n                    f"lineage={cap_lineage(depth)}",\n'''
new_cap = '''                    f"viable={body_attempts[name]:,}/{budget['max_node_candidates']:,} "\n                    f"unique_geometry={len(viable_geometry_seen.get(name, ())):,} "\n                    f"duplicates={max(0, body_attempts[name] - len(viable_geometry_seen.get(name, ()))):,} "\n                    f"lineage={cap_lineage(depth)}",\n'''
if text.count(old_cap) != 2:
    raise SystemExit(f"Safety stop: cap diagnostic block count={text.count(old_cap)}; expected 2")
text = text.replace(old_cap, new_cap)

TARGET.write_text(text, encoding="utf-8")
print("Added diagnostic-only viable candidate uniqueness accounting.")
