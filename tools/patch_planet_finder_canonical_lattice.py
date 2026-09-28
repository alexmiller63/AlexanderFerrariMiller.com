#!/usr/bin/env python3
"""Repair-once: add grandparent/parent/current body cap diagnostics."""
from pathlib import Path

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

anchor = '''    def viable_candidates(item, depth, *, consume_body_budget=True):
'''
helper = '''    def cap_lineage(depth):
        """Diagnostic-only viable counts for grandparent -> parent -> current."""
        parts = []
        for lineage_depth, role in (
            (depth - 2, "grandparent"),
            (depth - 1, "parent"),
            (depth, "current"),
        ):
            if 0 <= lineage_depth < len(order):
                lineage_name = order[lineage_depth][1][1]
                parts.append(
                    f"{role}[{lineage_name} depth={lineage_depth} "
                    f"viable={body_attempts.get(lineage_name, 0):,}]"
                )
        return " ".join(parts)

    def viable_candidates(item, depth, *, consume_body_budget=True):
'''
if text.count(anchor) != 1:
    raise SystemExit(f"Refusing repair: viable_candidates anchor count={text.count(anchor)}")
text = text.replace(anchor, helper, 1)

old = '''                    f"viable={body_attempts[name]:,}/{budget['max_node_candidates']:,}",
'''
new = '''                    f"viable={body_attempts[name]:,}/{budget['max_node_candidates']:,} "
                    f"lineage={cap_lineage(depth)}",
'''
count = text.count(old)
if count != 2:
    raise SystemExit(f"Refusing repair: expected 2 body-cap messages, found {count}")
text = text.replace(old, new)

TARGET.write_text(text, encoding="utf-8")
print("Added grandparent/parent/current viable-count diagnostics at body cap.")
