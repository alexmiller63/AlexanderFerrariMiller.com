#!/usr/bin/env python3
"""Repair-once patch: expose existing capped-body rejection diagnostics.

Diagnostic-only: no search, geometry, routing, budget, candidate, or controller
behavior is changed. Refuse to write unless the exact target occurs once.
"""
from pathlib import Path

TARGET = Path("tools/planet_finder_search_core.py")
OLD = '''        if reason.startswith("body-attempt-cap"):
            order_names = " > ".join(item[1][1] for item in order)
            diagnostic_print(
                f"Planet Finder {mode}: CAPPED SUMMARY order={order_index} "
                f"nodes={nodes:,} deepest={deepest}/{len(order)} "
                f"current_body={current_body} sequence={order_names}",
                flush=True,
            )
            return
'''
NEW = '''        if reason.startswith("body-attempt-cap"):
            order_names = " > ".join(item[1][1] for item in order)
            capped_stats = [
                (depth, name, stats)
                for (depth, name), stats in diagnostic_stats.items()
                if stats.get("blocked") == "body-candidate-cap"
            ]
            rejection_summary = ""
            if capped_stats:
                depth, name, stats = capped_stats[-1]
                rejection_summary = (
                    f" capped_body={name} depth={depth}/{len(order)} "
                    f"generated={stats.get('generated', 0):,} viable={stats.get('viable', 0):,} "
                    f"rejects[immutable-reserved={stats.get('immutable_reserved', 0):,},"
                    f"immutable-rim={stats.get('immutable_rim', 0):,},"
                    f"placed-overlap={stats.get('overlap', 0):,},"
                    f"existing-leader={stats.get('leader_existing', 0):,},"
                    f"route={stats.get('route', 0):,},"
                    f"leader-rim={stats.get('leader_rim', 0):,},"
                    f"leader-graze={stats.get('leader_graze', 0):,}]"
                )
            diagnostic_print(
                f"Planet Finder {mode}: CAPPED SUMMARY order={order_index} "
                f"nodes={nodes:,} deepest={deepest}/{len(order)} "
                f"current_body={current_body} sequence={order_names}"
                f"{rejection_summary}",
                flush=True,
            )
            return
'''

text = TARGET.read_text(encoding="utf-8")
count = text.count(OLD)
if count != 1:
    raise SystemExit(f"Refusing repair: expected capped-summary block exactly once, found {count}.")
TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
print("Capped-body rejection diagnostic patch applied.")
