#!/usr/bin/env python3
"""Mechanically install the two-pair/four-body Planet Finder endgame."""
from pathlib import Path

path = Path(__file__).with_name("planet_finder_search_core.py")
text = path.read_text(encoding="utf-8")

old_recurse = """                        if search(len(order)):\n                            return True\n"""
new_recurse = """                        # Continue after this pair.  At four remaining this\n                        # recurses into the second pair; at two remaining it\n                        # reaches the completed-layout base case.\n                        if search(first_depth + 2):\n                            return True\n"""
old_trigger = """        if depth == len(order) - 2:\n            return solve_final_pair(depth)\n"""
new_trigger = """        # Couple the last four bodies as two interacting pairs.  The same\n        # pair solver remains the two-body base case, so all four placements\n        # can backtrack together before returning to the ordinary DFS.\n        if depth == len(order) - 4:\n            return solve_final_pair(depth)\n\n        if depth == len(order) - 2:\n            return solve_final_pair(depth)\n"""

if text.count(old_recurse) != 1:
    raise RuntimeError(f"expected exactly one pair recursion site, found {text.count(old_recurse)}")
if text.count(old_trigger) != 1:
    raise RuntimeError(f"expected exactly one pair trigger site, found {text.count(old_trigger)}")

text = text.replace(old_recurse, new_recurse, 1).replace(old_trigger, new_trigger, 1)
path.write_text(text, encoding="utf-8")
print("Installed four-body/two-pair endgame.")
