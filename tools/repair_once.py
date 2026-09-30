#!/usr/bin/env python3
"""One-shot diagnostic: summarize recursive Mercury placements and Venus viability.

Instrumentation only.  Record each Mercury alignment candidate that reaches the
recursive alignment solver, whether its geometry is distinct, and the change in
Venus generated/viable counts while that Mercury placement owns the subtree.
Do not filter, reorder, score, or otherwise change search behavior.
"""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

CORE = Path("tools/planet_finder_search_core.py")
text = CORE.read_text(encoding="utf-8")

old = '''    mercury_candidate_stream = []\n    solutions = []\n'''
new = '''    mercury_candidate_stream = []\n    # Diagnostic only: recursive alignment Mercury placement -> Venus work.\n    # Never consulted by candidate generation or search decisions.\n    alignment_mercury_trials = []\n    solutions = []\n'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: Mercury diagnostic declaration anchor count={text.count(old)}; expected 1")
text = text.replace(old, new, 1)

old = '''        def try_candidate(candidate):\n            box, path = candidate\n            placed.append(box)\n            leaders.append(path)\n            leader_names.append(name)\n            staged[original_index] = (symbol, name, longitude, box, path)\n            solved = solve_alignment_members(group_index, next_remaining)\n            if not solved:\n                staged.pop(original_index, None)\n                leader_names.pop()\n                leaders.pop()\n                placed.pop()\n            return solved\n'''
new = '''        def try_candidate(candidate):\n            box, path = candidate\n            placed.append(box)\n            leaders.append(path)\n            leader_names.append(name)\n            staged[original_index] = (symbol, name, longitude, box, path)\n            mercury_before = None\n            mercury_signature = None\n            if name == "Mercury":\n                mercury_signature = (\n                    round(box.x, 3), round(box.y, 3), round(box.w, 3), round(box.h, 3),\n                    tuple((round(px, 3), round(py, 3)) for px, py in path),\n                )\n                mercury_before = {\n                    key: sum(\n                        stats.get(key, 0)\n                        for (diag_depth, diag_name), stats in diagnostic_stats.items()\n                        if diag_name == "Venus"\n                    )\n                    for key in ("generated", "viable")\n                }\n            try:\n                solved = solve_alignment_members(group_index, next_remaining)\n            finally:\n                if name == "Mercury":\n                    mercury_after = {\n                        key: sum(\n                            stats.get(key, 0)\n                            for (diag_depth, diag_name), stats in diagnostic_stats.items()\n                            if diag_name == "Venus"\n                        )\n                        for key in ("generated", "viable")\n                    }\n                    alignment_mercury_trials.append({\n                        "signature": mercury_signature,\n                        "box": (round(box.x, 2), round(box.y, 2), round(box.w, 2), round(box.h, 2)),\n                        "venus_generated": mercury_after["generated"] - mercury_before["generated"],\n                        "venus_viable": mercury_after["viable"] - mercury_before["viable"],\n                    })\n            if not solved:\n                staged.pop(original_index, None)\n                leader_names.pop()\n                leaders.pop()\n                placed.pop()\n            return solved\n'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: recursive alignment candidate anchor count={text.count(old)}; expected 1")
text = text.replace(old, new, 1)

old = '''            if uranus_venus_prefixes:\n                keys = ("generated", "viable", "immutable_reserved", "immutable_rim",\n'''
new = '''            if alignment_mercury_trials:\n                distinct = {}\n                for row in alignment_mercury_trials:\n                    sig = row["signature"]\n                    aggregate = distinct.setdefault(sig, {\n                        "box": row["box"], "visits": 0,\n                        "venus_generated": 0, "venus_viable": 0,\n                    })\n                    aggregate["visits"] += 1\n                    aggregate["venus_generated"] += row["venus_generated"]\n                    aggregate["venus_viable"] += row["venus_viable"]\n                ranked = sorted(\n                    distinct.values(),\n                    key=lambda row: (-row["venus_viable"], -row["venus_generated"], row["box"]),\n                )\n                samples = "; ".join(\n                    f"box={row['box']} visits={row['visits']} "\n                    f"V[gen={row['venus_generated']},ok={row['venus_viable']}]"\n                    for row in ranked[:20]\n                )\n                mercury_summary = (\n                    f"Planet Finder {mode}: ALIGNMENT MERCURY->VENUS SUMMARY "\n                    f"trials={len(alignment_mercury_trials):,} distinct={len(distinct):,} "\n                    f"venus-positive={sum(1 for row in distinct.values() if row['venus_viable'] > 0):,} "\n                    f"samples={samples}"\n                )\n                diagnostic_print(mercury_summary, flush=True)\n                summary_path = os.environ.get("GITHUB_STEP_SUMMARY")\n                if summary_path:\n                    with open(summary_path, "a", encoding="utf-8") as summary_file:\n                        summary_file.write("### Mercury alignment → Venus viability diagnostic\\n\\n" + mercury_summary + "\\n\\n")\n            if uranus_venus_prefixes:\n                keys = ("generated", "viable", "immutable_reserved", "immutable_rim",\n'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: diagnostic summary anchor count={text.count(old)}; expected 1")
text = text.replace(old, new, 1)

CORE.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")
print("Mercury-to-Venus alignment diagnostic installed. Repair Once is now OFF.")
