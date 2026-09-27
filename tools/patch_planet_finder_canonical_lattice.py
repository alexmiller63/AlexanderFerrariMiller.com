#!/usr/bin/env python3
"""Repair-once patch: classify a body-budget exception as a capped search.

Diagnostic-only: no search, geometry, routing, budget, candidate, or controller
behavior is changed. Refuse to write unless the exact target occurs once.
"""
from pathlib import Path

TARGET = Path("tools/planet_finder_search_core.py")
OLD = '''        dump_diagnostics(
            f"node budget exhausted at depth={exc.depth}/{len(order)} body={exc.name}"
        )
'''
NEW = '''        dump_diagnostics(
            f"body-attempt-cap depth={exc.depth}/{len(order)} body={exc.name}"
        )
'''

text = TARGET.read_text(encoding="utf-8")
count = text.count(OLD)
if count != 1:
    raise SystemExit(
        f"Refusing repair: expected cap diagnostic call exactly once, found {count}."
    )
TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
print("Capped-search diagnostic classification corrected.")
