#!/usr/bin/env python3
"""One-shot repair: add focused diagnostics for conjunction downstream branches."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old = '''                try:
                    downstream_solved = downstream()
                except DepthNodeBudgetExhausted as exc:
'''
new = '''                # Diagnostic-only snapshot for this complete conjunction blob.
                # It lets a downstream failure report what the ordinary DFS
                # actually reached, without changing geometry, ordering, caps,
                # clocks, or backtracking behavior.
                branch_nodes_before = nodes
                branch_backtracks_before = backtracks
                branch_deepest_before = deepest
                branch_attempts_before = dict(body_attempts)
                try:
                    downstream_solved = downstream()
                except DepthNodeBudgetExhausted as exc:
                    branch_attempt_deltas = {
                        body: body_attempts.get(body, 0) - branch_attempts_before.get(body, 0)
                        for body in body_attempts
                        if body_attempts.get(body, 0) != branch_attempts_before.get(body, 0)
                    }
                    diagnostic_print(
                        f"Planet Finder {mode}: CONJUNCTION DOWNSTREAM TRACE "
                        f"group={group_index + 1} candidate={blob_candidates} outcome=cap "
                        f"cap_body={exc.name} cap_depth={exc.depth} "
                        f"deepest_before={branch_deepest_before}/{len(order)} "
                        f"deepest_after={deepest}/{len(order)} "
                        f"nodes={nodes - branch_nodes_before} "
                        f"backtracks={backtracks - branch_backtracks_before} "
                        f"attempt_deltas={branch_attempt_deltas}",
                        level=2,
                        flush=True,
                    )
'''

old_barrier = '''                downstream_rejections += 1
                diagnostic_print(
                    f"Planet Finder {mode}: CONJUNCTION BLOB DOWNSTREAM BARRIER "
                    f"group={group_index + 1} candidate={blob_candidates} "
                    f"downstream_rejections={downstream_rejections} "
                    f"bodies={' > '.join(ordered_names)}; restoring whole blob",
                    flush=True,
                )
'''
new_barrier = '''                downstream_rejections += 1
                branch_attempt_deltas = {
                    body: body_attempts.get(body, 0) - branch_attempts_before.get(body, 0)
                    for body in body_attempts
                    if body_attempts.get(body, 0) != branch_attempts_before.get(body, 0)
                }
                diagnostic_print(
                    f"Planet Finder {mode}: CONJUNCTION BLOB DOWNSTREAM BARRIER "
                    f"group={group_index + 1} candidate={blob_candidates} "
                    f"downstream_rejections={downstream_rejections} "
                    f"bodies={' > '.join(ordered_names)}; restoring whole blob",
                    flush=True,
                )
                diagnostic_print(
                    f"Planet Finder {mode}: CONJUNCTION DOWNSTREAM TRACE "
                    f"group={group_index + 1} candidate={blob_candidates} outcome=barrier "
                    f"deepest_before={branch_deepest_before}/{len(order)} "
                    f"deepest_after={deepest}/{len(order)} "
                    f"nodes={nodes - branch_nodes_before} "
                    f"backtracks={backtracks - branch_backtracks_before} "
                    f"attempt_deltas={branch_attempt_deltas}",
                    level=2,
                    flush=True,
                )
'''

if text.count(old) != 1:
    raise SystemExit(f"Safety stop: downstream try block count={text.count(old)}; expected 1")
if text.count(old_barrier) != 1:
    raise SystemExit(f"Safety stop: downstream barrier block count={text.count(old_barrier)}; expected 1")

text = text.replace(old, new, 1)
text = text.replace(old_barrier, new_barrier, 1)
TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Added diagnostic-only conjunction downstream traces: per blob, report "
    "deepest DFS reach, node/backtrack cost, body-attempt deltas, and cap body; "
    "solver behavior is unchanged; Repair Once is now OFF."
)
