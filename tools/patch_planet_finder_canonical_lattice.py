#!/usr/bin/env python3
"""Repair-once: extend body-cap diagnostics across all descendants."""
from pathlib import Path

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old = '''                # Diagnostic only: when a parent body consumes its viable
                # candidate allowance because every child subtree fails, show
                # the immediate descendant's aggregate behavior.  This makes
                # the actual squeaky wheel visible without changing search,
                # candidate accounting, ordering, geometry, or budgets.
                child_depth = depth + 1
                if child_depth < len(order):
                    child_name = order[child_depth][1][1]
                    child_stats = diagnostic_stats.get((child_depth, child_name), {})
                    rejection_summary += (
                        f" child[{child_name} depth={child_depth}/{len(order)} "
                        f"visits={depth_visits.get(child_depth, 0):,} "
                        f"dead_ends={dead_end_visits.get((child_depth, child_name), 0):,} "
                        f"generated={child_stats.get('generated', 0):,} "
                        f"viable={child_stats.get('viable', 0):,} "
                        f"rejects[immutable-reserved={child_stats.get('immutable_reserved', 0):,},"
                        f"immutable-rim={child_stats.get('immutable_rim', 0):,},"
                        f"placed-overlap={child_stats.get('overlap', 0):,},"
                        f"existing-leader={child_stats.get('leader_existing', 0):,},"
                        f"route={child_stats.get('route', 0):,},"
                        f"leader-rim={child_stats.get('leader_rim', 0):,},"
                        f"leader-graze={child_stats.get('leader_graze', 0):,}]]"
                    )
'''

new = '''                # Diagnostic only: when a parent body consumes its viable
                # candidate allowance because every descendant subtree fails,
                # show aggregate behavior at every deeper depth.  This extends
                # the visibility from the immediate child through the full
                # descendant chain without changing search, accounting,
                # ordering, geometry, or budgets.
                for descendant_depth in range(depth + 1, len(order)):
                    descendant_name = order[descendant_depth][1][1]
                    descendant_stats = diagnostic_stats.get(
                        (descendant_depth, descendant_name), {}
                    )
                    rejection_summary += (
                        f" descendant[{descendant_name} "
                        f"depth={descendant_depth}/{len(order)} "
                        f"visits={depth_visits.get(descendant_depth, 0):,} "
                        f"dead_ends={dead_end_visits.get((descendant_depth, descendant_name), 0):,} "
                        f"generated={descendant_stats.get('generated', 0):,} "
                        f"viable={descendant_stats.get('viable', 0):,} "
                        f"rejects[immutable-reserved={descendant_stats.get('immutable_reserved', 0):,},"
                        f"immutable-rim={descendant_stats.get('immutable_rim', 0):,},"
                        f"placed-overlap={descendant_stats.get('overlap', 0):,},"
                        f"existing-leader={descendant_stats.get('leader_existing', 0):,},"
                        f"route={descendant_stats.get('route', 0):,},"
                        f"leader-rim={descendant_stats.get('leader_rim', 0):,},"
                        f"leader-graze={descendant_stats.get('leader_graze', 0):,}]]"
                    )
'''

count = text.count(old)
if count != 1:
    raise SystemExit(
        f"Refusing repair: expected immediate-descendant diagnostic exactly once, found {count}"
    )

TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Extended body-cap diagnostics across all descendant depths.")
