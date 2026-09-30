#!/usr/bin/env python3
"""One-shot: compact W01 alignment depth-8/9 backtracking diagnostic.

Instrumentation only. It records the body selected at depth 8, how often that
depth is entered, how many depth-8 candidates are tried, and whether returning
to depth 7 produces genuinely different parent placements. Solver behavior,
candidate order, geometry, and budgets are unchanged. Self-disables.
"""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

CORE = Path("tools/planet_finder_search_core.py")
text = CORE.read_text(encoding="utf-8")

anchor = '''        termination_reason = "exhausted"

        def assign(remaining, available, chosen):
'''
replacement = '''        termination_reason = "exhausted"
        depth89 = {
            "depth8_entries": 0,
            "depth8_body": {},
            "depth8_candidate_tries": 0,
            "depth7_entries": 0,
            "depth7_parent_signatures": set(),
        }

        def assign(remaining, available, chosen):
'''
if text.count(anchor) != 1:
    raise SystemExit(f"Safety stop: alignment diagnostic anchor count={text.count(anchor)}")
text = text.replace(anchor, replacement, 1)

anchor = '''            name = min(remaining, key=lambda candidate: (len(available[candidate]), order_names.index(candidate)))
            others = [candidate for candidate in remaining if candidate != name]
            for row in available[name]:
                nodes += 1
'''
replacement = '''            name = min(remaining, key=lambda candidate: (len(available[candidate]), order_names.index(candidate)))
            if depth_here == 8:
                depth89["depth8_entries"] += 1
                depth89["depth8_body"][name] = depth89["depth8_body"].get(name, 0) + 1
            elif depth_here == 7:
                depth89["depth7_entries"] += 1
                signature = tuple(
                    (member, round(chosen[member][0], 3), round(chosen[member][1], 3))
                    for member in sorted(chosen)
                )
                depth89["depth7_parent_signatures"].add(signature)
            others = [candidate for candidate in remaining if candidate != name]
            for row in available[name]:
                if depth_here == 8:
                    depth89["depth8_candidate_tries"] += 1
                nodes += 1
'''
if text.count(anchor) != 1:
    raise SystemExit(f"Safety stop: alignment assign anchor count={text.count(anchor)}")
text = text.replace(anchor, replacement, 1)

anchor = '''            f"- Planned-path rejects: {assign_rejects['planned_path']:,}",
            f"- Path causes: route={alignment_path_rejects['route']:,}, "
'''
replacement = '''            f"- Planned-path rejects: {assign_rejects['planned_path']:,}",
            f"- Depth 8/9 entries: {depth89['depth8_entries']:,}",
            f"- Depth 8/9 selected body: {depth89['depth8_body']}",
            f"- Depth 8/9 candidate tries: {depth89['depth8_candidate_tries']:,}",
            f"- Depth 7/9 entries: {depth89['depth7_entries']:,}",
            f"- Distinct depth 7 parent placements: {len(depth89['depth7_parent_signatures']):,}",
            f"- Path causes: route={alignment_path_rejects['route']:,}, "
'''
if text.count(anchor) != 1:
    raise SystemExit(f"Safety stop: alignment summary anchor count={text.count(anchor)}")
text = text.replace(anchor, replacement, 1)

anchor = '''            f"rim={alignment_path_rejects['rim_hit']:,},graze={alignment_path_rejects['leader_graze']:,}]",
            flush=True,
        )
'''
replacement = '''            f"rim={alignment_path_rejects['rim_hit']:,},graze={alignment_path_rejects['leader_graze']:,}] "
            f"depth8[entries={depth89['depth8_entries']:,},body={depth89['depth8_body']},"
            f"tries={depth89['depth8_candidate_tries']:,}] "
            f"depth7[entries={depth89['depth7_entries']:,},"
            f"distinct-parents={len(depth89['depth7_parent_signatures']):,}]",
            flush=True,
        )
'''
if text.count(anchor) != 1:
    raise SystemExit(f"Safety stop: alignment print anchor count={text.count(anchor)}")
text = text.replace(anchor, replacement, 1)

CORE.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8").replace("ENABLED = True", "ENABLED = False", 1)
me.write_text(self_text, encoding="utf-8")
print("Installed compact alignment 8/9 backtracking diagnostic. Solver unchanged. Repair Once is now OFF.")
