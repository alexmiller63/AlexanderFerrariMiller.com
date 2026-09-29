#!/usr/bin/env python3
"""One-shot diagnostic: replace noisy alignment-cliff tracing with one compact summary."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

# Remove the per-candidate cliff trace from planned_paths; retain counters/samples instead.
old_trace = '''                if path is None or label_hit or rim_hit or graze:
                    if os.environ.get("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF") == "1":
                        prior_summary = [
                            [(round(px, 1), round(py, 1)) for px, py in prior]
                            for prior in prior_paths
                        ]
                        path_summary = None if path is None else [
                            (round(px, 1), round(py, 1)) for px, py in path
                        ]
                        diagnostic_print(
                            f"Planet Finder {mode}: ALIGNMENT CLIFF TRACE body={name} "
                            f"route_none={path is None} label_hit={label_hit} rim_hit={rim_hit} "
                            f"leader_graze={graze} chosen={','.join(chosen.keys())} "
                            f"path={path_summary} prior_paths={prior_summary}",
                            level=1, flush=True,
                        )
                    return None
'''
new_trace = '''                if path is None or label_hit or rim_hit or graze:
                    if path is None:
                        alignment_path_rejects["route"] += 1
                        sample_key = "route"
                    elif label_hit:
                        alignment_path_rejects["label_hit"] += 1
                        sample_key = "label_hit"
                    elif rim_hit:
                        alignment_path_rejects["rim_hit"] += 1
                        sample_key = "rim_hit"
                    else:
                        alignment_path_rejects["leader_graze"] += 1
                        sample_key = "leader_graze"
                    if sample_key not in alignment_samples:
                        alignment_samples[sample_key] = (
                            f"body={name} chosen={','.join(chosen.keys())} "
                            f"path={None if path is None else [(round(px,1), round(py,1)) for px,py in path]}"
                        )
                    return None
'''
if text.count(old_trace) != 1:
    raise SystemExit("Safety stop: noisy alignment cliff trace did not match exactly once")
text = text.replace(old_trace, new_trace, 1)

# Add path counters before planned_paths uses them.
old_group = '''        group_names = [[item[1][1] for item in group] for group in groups]

        def label_angle(row, reference):
'''
new_group = '''        group_names = [[item[1][1] for item in group] for group in groups]
        alignment_path_rejects = {"route": 0, "label_hit": 0, "rim_hit": 0, "leader_graze": 0}
        alignment_samples = {}

        def label_angle(row, reference):
'''
if text.count(old_group) != 1:
    raise SystemExit("Safety stop: group_names insertion point did not match exactly once")
text = text.replace(old_group, new_group, 1)

# Remove noisy per-candidate Venus/Sun legality prints from ordinary candidate generation.
start_marker = '''            if own_label_bad:\n                if os.environ.get("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF") == "1" and name in ("Venus", "Sun"):\n'''
if start_marker not in text:
    raise SystemExit("Safety stop: own-label noisy trace start not found")
start = text.index(start_marker)
end_marker = '''                rejected_leader += 1\n                stats["leader"] += 1\n                stats["leader_graze"] += 1\n                continue\n'''
end = text.index(end_marker, start) + len(end_marker)
text = text[:start] + '''            if own_label_bad:\n                rejected_leader += 1\n                stats["leader"] += 1\n                stats["leader_graze"] += 1\n                continue\n''' + text[end:]

start_marker = '''            if too_close:\n                if os.environ.get("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF") == "1" and name in ("Venus", "Sun"):\n'''
if start_marker not in text:
    raise SystemExit("Safety stop: leader-close noisy trace start not found")
start = text.index(start_marker)
accept_marker = '''            # Diagnostic-only geometry signature.'''
end = text.index(accept_marker, start)
text = text[:start] + '''            if too_close:\n                rejected_leader += 1\n                stats["leader"] += 1\n                stats["leader_graze"] += 1\n                continue\n''' + text[end:]

# Split the combined rejection bucket and capture one representative sample.
old_init = '''        assign_rejects = {"empty_future": 0, "order_or_path": 0}
        deepest_alignment_choice = 0
'''
new_init = '''        assign_rejects = {"empty_future": 0, "circular_order": 0, "planned_path": 0}
        deepest_alignment_choice = 0
        termination_reason = "exhausted"
'''
if text.count(old_init) != 1:
    raise SystemExit("Safety stop: assign rejection init did not match exactly once")
text = text.replace(old_init, new_init, 1)

old_nonlocal = '''            nonlocal nodes, deepest_alignment_choice
'''
new_nonlocal = '''            nonlocal nodes, deepest_alignment_choice, termination_reason
'''
if text.count(old_nonlocal) != 1:
    raise SystemExit("Safety stop: assign nonlocal did not match exactly once")
text = text.replace(old_nonlocal, new_nonlocal, 1)

old_limit = '''                    if os.environ.get("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF") == "1":
                        diagnostic_print(
                            f"Planet Finder {mode}: ALIGNMENT SEARCH EXPLOSION nodes={nodes} "
                            f"depth={depth_here}/{len(order_names)} next={name} "
                            f"chosen={','.join(chosen.keys()) or '-'} "
                            f"visits={assign_visits} rejects={assign_rejects}",
                            level=1, flush=True,
                        )
                    return None
'''
new_limit = '''                    termination_reason = "node-limit" if nodes > 50000 else "deadline"
                    if "termination" not in alignment_samples:
                        alignment_samples["termination"] = (
                            f"depth={depth_here}/{len(order_names)} next={name} "
                            f"chosen={','.join(chosen.keys()) or '-'}"
                        )
                    return None
'''
if text.count(old_limit) != 1:
    raise SystemExit("Safety stop: noisy explosion print did not match exactly once")
text = text.replace(old_limit, new_limit, 1)

old_split = '''                trial = {**chosen, name: row}
                if not ordered(trial) or planned_paths(trial) is None:
                    assign_rejects["order_or_path"] += 1
                    continue
'''
new_split = '''                trial = {**chosen, name: row}
                if not ordered(trial):
                    assign_rejects["circular_order"] += 1
                    if "circular_order" not in alignment_samples:
                        alignment_samples["circular_order"] = (
                            f"chosen={','.join(trial.keys())} "
                            + " angles=" + ",".join(
                                f"{member}:{label_angle(trial[member], longitudes[group_names[0][0]] - 90.0):.3f}"
                                for member in group_names[0] if member in trial
                            )
                        )
                    continue
                if planned_paths(trial) is None:
                    assign_rejects["planned_path"] += 1
                    continue
'''
if text.count(old_split) != 1:
    raise SystemExit("Safety stop: combined order/path rejection did not match exactly once")
text = text.replace(old_split, new_split, 1)

# Replace pool/winner/preplacement chatter with one compact summary, written to Actions summary when available.
pool_start = '''        # Diagnostic fingerprint for the Venus/Sun threshold ladder.'''
pool_end = '''        return result\n'''
if pool_start not in text:
    raise SystemExit("Safety stop: pool diagnostic block start not found")
start = text.index(pool_start)
end = text.index(pool_end, start) + len(pool_end)
replacement = '''        result = assign(order_names, pools, {})
        planned = result[0] if result else {}
        if result is not None:
            termination_reason = "success"
        summary_lines = [
            f"### Planet Finder alignment diagnostic — {mode}",
            "",
            f"- Members: {', '.join(order_names)}",
            f"- Result: {termination_reason}",
            f"- Nodes: {nodes:,}",
            f"- Deepest: {deepest_alignment_choice}/{len(order_names)}",
            f"- Complete alignment constructed: {'yes' if result is not None else 'no'}",
            f"- Visits by depth: {assign_visits}",
            f"- Empty-future prunes: {assign_rejects['empty_future']:,}",
            f"- Circular-order rejects: {assign_rejects['circular_order']:,}",
            f"- Planned-path rejects: {assign_rejects['planned_path']:,}",
            f"- Path causes: route={alignment_path_rejects['route']:,}, "
            f"label_hit={alignment_path_rejects['label_hit']:,}, "
            f"rim_hit={alignment_path_rejects['rim_hit']:,}, "
            f"leader_graze={alignment_path_rejects['leader_graze']:,}",
        ]
        if alignment_samples:
            summary_lines += ["", "Representative first failures:"]
            summary_lines += [f"- {key}: {value}" for key, value in alignment_samples.items()]
        summary = "\\n".join(summary_lines)
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as summary_file:
                summary_file.write(summary + "\\n\\n")
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT SUMMARY result={termination_reason} "
            f"nodes={nodes:,} deepest={deepest_alignment_choice}/{len(order_names)} "
            f"rejects[empty={assign_rejects['empty_future']:,},order={assign_rejects['circular_order']:,},"
            f"path={assign_rejects['planned_path']:,}] "
            f"path-causes[route={alignment_path_rejects['route']:,},label={alignment_path_rejects['label_hit']:,},"
            f"rim={alignment_path_rejects['rim_hit']:,},graze={alignment_path_rejects['leader_graze']:,}]",
            flush=True,
        )
        return result
'''
text = text[:start] + replacement + text[end:]

TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Replaced alignment-cliff log flood with compact counters, split circular-order/path failures, "
    "representative samples, and GitHub Actions step summary output. No solver behavior changed. "
    "Repair Once is now OFF."
)
