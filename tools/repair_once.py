#!/usr/bin/env python3
"""One-shot repair: add diagnostic-only Pluto -> Venus DFS boundary accounting."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old = '''    viable_geometry_seen = {}
    # Diagnostic only: summarize how Mercury's admitted candidates traverse
'''
new = '''    viable_geometry_seen = {}
    # Diagnostic only: record what happens to Venus under each individually
    # viable Pluto parent placement. This does not alter search behavior.
    pluto_venus_prefixes = []
    # Diagnostic only: summarize how Mercury's admitted candidates traverse
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: viable_geometry_seen insertion point did not match exactly once")
text = text.replace(old, new, 1)

old = '''            child_deepest_before = deepest
            child_nodes_before = nodes
            child_backtracks_before = backtracks
            try:
'''
new = '''            child_deepest_before = deepest
            child_nodes_before = nodes
            child_backtracks_before = backtracks
            pv_before = None
            if name == "Pluto" and depth + 1 < len(order) and order[depth + 1][1][1] == "Venus":
                venus_stats = diagnostic_stats.get((depth + 1, "Venus"), {})
                pv_before = {
                    key: venus_stats.get(key, 0)
                    for key in ("generated", "viable", "immutable_reserved", "immutable_rim",
                                "overlap", "leader_existing", "route", "leader_rim", "leader_graze")
                }
            try:
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: child DFS snapshot insertion point did not match exactly once")
text = text.replace(old, new, 1)

old = '''                staged.pop(original_index, None)
                leaders.pop()
                leader_names.pop()
                placed.pop()

            backtracks += 1
'''
new = '''                staged.pop(original_index, None)
                leaders.pop()
                leader_names.pop()
                placed.pop()

            if pv_before is not None:
                venus_stats = diagnostic_stats.get((depth + 1, "Venus"), {})
                delta = {
                    key: venus_stats.get(key, 0) - pv_before.get(key, 0)
                    for key in pv_before
                }
                pluto_venus_prefixes.append(delta)

            backtracks += 1
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: child DFS delta insertion point did not match exactly once")
text = text.replace(old, new, 1)

old = '''            diagnostic_print(
                f"Planet Finder {mode}: CAPPED SUMMARY order={order_index} "
                f"nodes={nodes:,} deepest={deepest}/{len(order)} "
                f"current_body={current_body} sequence={order_names}"
                f"{rejection_summary}{validation_summary}",
                flush=True,
            )
            return
'''
new = '''            diagnostic_print(
                f"Planet Finder {mode}: CAPPED SUMMARY order={order_index} "
                f"nodes={nodes:,} deepest={deepest}/{len(order)} "
                f"current_body={current_body} sequence={order_names}"
                f"{rejection_summary}{validation_summary}",
                flush=True,
            )
            if pluto_venus_prefixes:
                keys = ("generated", "viable", "immutable_reserved", "immutable_rim",
                        "overlap", "leader_existing", "route", "leader_rim", "leader_graze")
                totals = {key: sum(row[key] for row in pluto_venus_prefixes) for key in keys}
                zero_viable = sum(1 for row in pluto_venus_prefixes if row["viable"] == 0)
                diagnostic_print(
                    f"Planet Finder {mode}: PLUTO-VENUS PREFIX SUMMARY "
                    f"parents={len(pluto_venus_prefixes):,} zero-viable={zero_viable:,} "
                    f"venus-generated={totals['generated']:,} venus-viable={totals['viable']:,} "
                    f"rejects[immutable-reserved={totals['immutable_reserved']:,},"
                    f"immutable-rim={totals['immutable_rim']:,},"
                    f"placed-overlap={totals['overlap']:,},"
                    f"existing-leader={totals['leader_existing']:,},"
                    f"route={totals['route']:,},leader-rim={totals['leader_rim']:,},"
                    f"leader-graze={totals['leader_graze']:,}]",
                    flush=True,
                )
            return
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: capped summary insertion point did not match exactly once")
text = text.replace(old, new, 1)

TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Added diagnostic-only Pluto -> Venus per-parent rejection accounting and compact capped summary. "
    "No geometry, ordering, candidate budgets, or DFS behavior changed. Repair Once is now OFF."
)
