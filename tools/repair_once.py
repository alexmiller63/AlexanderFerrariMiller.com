#!/usr/bin/env python3
"""One-shot repair: instrument the W36 Pluto > Uranus > Venus dead end.

Diagnostic only. Solver ordering, candidate geometry, legality, routing, caps,
and backtracking are unchanged. The added compact summary records each viable
Uranus prefix under the already-placed Pluto parent and the Venus rejection
mix beneath it.
"""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old = '''    # Diagnostic only: record what happens to Venus under each individually
    # viable Pluto parent placement. This does not alter search behavior.
    pluto_venus_prefixes = []
'''
new = '''    # Diagnostic only: record what happens to Venus under individually viable
    # parent placements. The Uranus form exposes the exact W36
    # Pluto > Uranus > Venus terminal chain without altering search behavior.
    pluto_venus_prefixes = []
    uranus_venus_prefixes = []
'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: diagnostic-list anchor count={text.count(old)}; expected 1")
text = text.replace(old, new, 1)

old = '''            child_backtracks_before = backtracks
            pv_before = None
            if name == "Pluto" and depth + 1 < len(order) and order[depth + 1][1][1] == "Venus":
                venus_stats = diagnostic_stats.get((depth + 1, "Venus"), {})
                pv_before = {
                    key: venus_stats.get(key, 0)
                    for key in ("generated", "viable", "immutable_reserved", "immutable_rim",
                                "overlap", "leader_existing", "route", "leader_rim", "leader_graze")
                }
'''
new = '''            child_backtracks_before = backtracks
            pv_before = None
            uv_before = None
            if name == "Pluto" and depth + 1 < len(order) and order[depth + 1][1][1] == "Venus":
                venus_stats = diagnostic_stats.get((depth + 1, "Venus"), {})
                pv_before = {
                    key: venus_stats.get(key, 0)
                    for key in ("generated", "viable", "immutable_reserved", "immutable_rim",
                                "overlap", "leader_existing", "route", "leader_rim", "leader_graze")
                }
            if name == "Uranus" and depth + 1 < len(order) and order[depth + 1][1][1] == "Venus":
                venus_stats = diagnostic_stats.get((depth + 1, "Venus"), {})
                uv_before = {
                    key: venus_stats.get(key, 0)
                    for key in ("generated", "viable", "immutable_reserved", "immutable_rim",
                                "overlap", "leader_existing", "route", "leader_rim", "leader_graze")
                }
'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: prefix-before anchor count={text.count(old)}; expected 1")
text = text.replace(old, new, 1)

old = '''            if pv_before is not None:
                venus_stats = diagnostic_stats.get((depth + 1, "Venus"), {})
                delta = {
                    key: venus_stats.get(key, 0) - pv_before.get(key, 0)
                    for key in pv_before
                }
                pluto_venus_prefixes.append(delta)

            backtracks += 1
'''
new = '''            if pv_before is not None:
                venus_stats = diagnostic_stats.get((depth + 1, "Venus"), {})
                delta = {
                    key: venus_stats.get(key, 0) - pv_before.get(key, 0)
                    for key in pv_before
                }
                pluto_venus_prefixes.append(delta)
            if uv_before is not None:
                venus_stats = diagnostic_stats.get((depth + 1, "Venus"), {})
                delta = {
                    key: venus_stats.get(key, 0) - uv_before.get(key, 0)
                    for key in uv_before
                }
                # Keep just enough parent geometry to distinguish whether the
                # same Uranus region repeatedly strands Venus. Pluto is still
                # present in placed[] at this point and is represented by the
                # enclosing DFS prefix; no search state is changed.
                delta["uranus_box"] = (round(box.x, 1), round(box.y, 1), round(box.w, 1), round(box.h, 1))
                delta["uranus_path"] = tuple((round(px, 1), round(py, 1)) for px, py in path)
                uranus_venus_prefixes.append(delta)

            backtracks += 1
'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: prefix-after anchor count={text.count(old)}; expected 1")
text = text.replace(old, new, 1)

old = '''            if pluto_venus_prefixes:
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
new = '''            if pluto_venus_prefixes:
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
            if uranus_venus_prefixes:
                keys = ("generated", "viable", "immutable_reserved", "immutable_rim",
                        "overlap", "leader_existing", "route", "leader_rim", "leader_graze")
                totals = {key: sum(row[key] for row in uranus_venus_prefixes) for key in keys}
                zero_viable = sum(1 for row in uranus_venus_prefixes if row["viable"] == 0)
                worst = sorted(
                    uranus_venus_prefixes,
                    key=lambda row: (row["viable"], -sum(row[key] for key in keys[2:])),
                )[:5]
                samples = "; ".join(
                    f"box={row['uranus_box']} path={row['uranus_path']} "
                    f"V[gen={row['generated']},ok={row['viable']},res={row['immutable_reserved']},"
                    f"rim={row['immutable_rim']},ov={row['overlap']},lead={row['leader_existing']},"
                    f"route={row['route']},lrim={row['leader_rim']},graze={row['leader_graze']}]"
                    for row in worst
                )
                summary = (
                    f"Planet Finder {mode}: W36 URANUS-VENUS DEAD-END SUMMARY "
                    f"prefixes={len(uranus_venus_prefixes):,} zero-viable={zero_viable:,} "
                    f"venus-generated={totals['generated']:,} venus-viable={totals['viable']:,} "
                    f"rejects[immutable-reserved={totals['immutable_reserved']:,},"
                    f"immutable-rim={totals['immutable_rim']:,},placed-overlap={totals['overlap']:,},"
                    f"existing-leader={totals['leader_existing']:,},route={totals['route']:,},"
                    f"leader-rim={totals['leader_rim']:,},leader-graze={totals['leader_graze']:,}] "
                    f"samples={samples}"
                )
                diagnostic_print(summary, flush=True)
                summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
                if summary_path:
                    with open(summary_path, "a", encoding="utf-8") as summary_file:
                        summary_file.write("### W36 Uranus → Venus dead-end diagnostic\\n\\n" + summary + "\\n\\n")
            return
'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: capped-summary anchor count={text.count(old)}; expected 1")
text = text.replace(old, new, 1)

TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print("Added diagnostic-only W36 Uranus -> Venus dead-end summary; solver behavior unchanged. Repair Once is now OFF.")
