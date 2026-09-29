#!/usr/bin/env python3
"""One-shot diagnostic: expose the 1.7-degree alignment search explosion."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old = '''        nodes = 0

        def assign(remaining, available, chosen):
            nonlocal nodes
            if not remaining:
                return (chosen, planned_paths(chosen))
            name = min(remaining, key=lambda candidate: (len(available[candidate]), order_names.index(candidate)))
            others = [candidate for candidate in remaining if candidate != name]
            for row in available[name]:
                nodes += 1
                if nodes > 50000 or (refinement_deadline is not None and
                                     time.monotonic() >= refinement_deadline):
                    return None
'''
new = '''        nodes = 0
        assign_visits = {}
        assign_rejects = {"empty_future": 0, "order_or_path": 0}
        deepest_alignment_choice = 0

        def assign(remaining, available, chosen):
            nonlocal nodes, deepest_alignment_choice
            depth_here = len(chosen)
            deepest_alignment_choice = max(deepest_alignment_choice, depth_here)
            assign_visits[depth_here] = assign_visits.get(depth_here, 0) + 1
            if not remaining:
                return (chosen, planned_paths(chosen))
            name = min(remaining, key=lambda candidate: (len(available[candidate]), order_names.index(candidate)))
            others = [candidate for candidate in remaining if candidate != name]
            for row in available[name]:
                nodes += 1
                if nodes > 50000 or (refinement_deadline is not None and
                                     time.monotonic() >= refinement_deadline):
                    if os.environ.get("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF") == "1":
                        diagnostic_print(
                            f"Planet Finder {mode}: ALIGNMENT SEARCH EXPLOSION nodes={nodes} "
                            f"depth={depth_here}/{len(order_names)} next={name} "
                            f"chosen={','.join(chosen.keys()) or '-'} "
                            f"visits={assign_visits} rejects={assign_rejects}",
                            level=1, flush=True,
                        )
                    return None
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: alignment assign header did not match exactly once")
text = text.replace(old, new, 1)

old2 = '''                if any(not next_available[candidate] for candidate in others):
                    continue
                trial = {**chosen, name: row}
                if not ordered(trial) or planned_paths(trial) is None:
                    continue
'''
new2 = '''                if any(not next_available[candidate] for candidate in others):
                    assign_rejects["empty_future"] += 1
                    continue
                trial = {**chosen, name: row}
                if not ordered(trial) or planned_paths(trial) is None:
                    assign_rejects["order_or_path"] += 1
                    continue
'''
if text.count(old2) != 1:
    raise SystemExit("Safety stop: alignment rejection block did not match exactly once")
text = text.replace(old2, new2, 1)

old3 = '''        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT PREPLACEMENT "
            f"planned={len(planned)}/{len(order_names)} nodes={nodes}",
            flush=True,
        )
'''
new3 = '''        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT PREPLACEMENT "
            f"planned={len(planned)}/{len(order_names)} nodes={nodes} "
            f"deepest={deepest_alignment_choice}/{len(order_names)} "
            f"visits={assign_visits} rejects={assign_rejects}",
            flush=True,
        )
'''
if text.count(old3) != 1:
    raise SystemExit("Safety stop: alignment preplacement summary did not match exactly once")
text = text.replace(old3, new3, 1)

TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Added diagnostic-only alignment search-tree counters: nodes, depth visits, "
    "empty-future prunes, and order/path rejections. No solver behavior changed. "
    "Repair Once is now OFF."
)
