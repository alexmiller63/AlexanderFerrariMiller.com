#!/usr/bin/env python3
"""Repair-once patch: let conjunction blobs own downstream backtracking.

A complete conjunction blob is a real DFS node.  If downstream ordinary search
hits its per-body candidate cap, restore the whole blob *and* the downstream
body-attempt budget, then try the next internally valid blob.  Only after every
blob candidate has failed may the cap escape to the outer squeaky-wheel
controller.  A true wall-clock/runtime abort still propagates immediately,
but only after restoring blob state.

No geometry, routing, collision, candidate-pool, or cap value is changed.
Refuse to write unless every exact target occurs once.
"""
from pathlib import Path

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"Refusing repair: expected {label} exactly once, found {count}"
        )
    text = text.replace(old, new, 1)


replace_once(
'''        blob_candidates = 0
        downstream_rejections = 0

        def assign(depth):
            nonlocal blob_candidates, downstream_rejections
''',
'''        blob_candidates = 0
        downstream_rejections = 0
        # A descendant body cap is local evidence against the current blob,
        # not permission to jump across the conjunction recursion.  Remember
        # one such cap so it can reach the outer controller only after every
        # blob candidate has had its own downstream search budget.
        pending_budget_exhaustion = None

        def assign(depth):
            nonlocal blob_candidates, downstream_rejections
            nonlocal pending_budget_exhaustion
''',
"blob recursion state",
)

replace_once(
'''                placed_mark = len(placed)
                leaders_mark = len(leaders)
                names_mark = len(leader_names)
                staged_before = set(staged)
                for original_index, (symbol, name, longitude) in group_items:
                    box = chosen[name][2]
                    leader = chosen_paths[name]
                    placed.append(box)
                    leaders.append(leader)
                    leader_names.append(name)
                    staged[original_index] = (symbol, name, longitude, box, leader)
                if downstream():
                    diagnostic_print(
                        f"Planet Finder {mode}: CONJUNCTION BLOB COMPATIBLE "
                        f"group={group_index + 1} candidate={blob_candidates} "
                        f"bodies={' > '.join(ordered_names)}",
                        flush=True,
                    )
                    return True
                downstream_rejections += 1
                diagnostic_print(
                    f"Planet Finder {mode}: CONJUNCTION BLOB DOWNSTREAM BARRIER "
                    f"group={group_index + 1} candidate={blob_candidates} "
                    f"downstream_rejections={downstream_rejections} "
                    f"bodies={' > '.join(ordered_names)}; restoring whole blob",
                    flush=True,
                )
                del placed[placed_mark:]
                del leaders[leaders_mark:]
                del leader_names[names_mark:]
                for key in list(staged):
                    if key not in staged_before:
                        staged.pop(key, None)
                return False
''',
'''                placed_mark = len(placed)
                leaders_mark = len(leaders)
                names_mark = len(leader_names)
                staged_before = set(staged)
                # Downstream candidate counts belong to this blob branch.  A
                # rejected blob must not poison its sibling by consuming the
                # sibling's 200-candidate allowance.
                body_attempts_before = dict(body_attempts)

                def restore_blob_branch():
                    del placed[placed_mark:]
                    del leaders[leaders_mark:]
                    del leader_names[names_mark:]
                    for key in list(staged):
                        if key not in staged_before:
                            staged.pop(key, None)
                    body_attempts.clear()
                    body_attempts.update(body_attempts_before)

                for original_index, (symbol, name, longitude) in group_items:
                    box = chosen[name][2]
                    leader = chosen_paths[name]
                    placed.append(box)
                    leaders.append(leader)
                    leader_names.append(name)
                    staged[original_index] = (symbol, name, longitude, box, leader)
                try:
                    downstream_solved = downstream()
                except DepthNodeBudgetExhausted as exc:
                    # This blob exhausted a descendant search allowance.  That
                    # is a failed child branch: restore it and let assign()
                    # continue to the next complete conjunction blob.
                    restore_blob_branch()
                    if pending_budget_exhaustion is None:
                        pending_budget_exhaustion = exc
                    downstream_rejections += 1
                    diagnostic_print(
                        f"Planet Finder {mode}: CONJUNCTION BLOB DOWNSTREAM CAP "
                        f"group={group_index + 1} candidate={blob_candidates} "
                        f"body={exc.name} depth={exc.depth}; "
                        f"restoring whole blob and trying next blob",
                        flush=True,
                    )
                    return False
                except Exception:
                    # Wall-clock and other true controller aborts still escape,
                    # but never leave a half-staged conjunction behind.
                    restore_blob_branch()
                    raise

                if downstream_solved:
                    diagnostic_print(
                        f"Planet Finder {mode}: CONJUNCTION BLOB COMPATIBLE "
                        f"group={group_index + 1} candidate={blob_candidates} "
                        f"bodies={' > '.join(ordered_names)}",
                        flush=True,
                    )
                    return True
                downstream_rejections += 1
                diagnostic_print(
                    f"Planet Finder {mode}: CONJUNCTION BLOB DOWNSTREAM BARRIER "
                    f"group={group_index + 1} candidate={blob_candidates} "
                    f"downstream_rejections={downstream_rejections} "
                    f"bodies={' > '.join(ordered_names)}; restoring whole blob",
                    flush=True,
                )
                restore_blob_branch()
                return False
''',
"atomic blob downstream boundary",
)

replace_once(
'''        if not assign(0):
            raw_escape_blockers = conjunction_route_diagnostics.get("escape_blocked_by", {})
''',
'''        if not assign(0):
            # All sibling blobs have now been tried.  Only at this point may a
            # descendant cap become a squeaky-wheel signal for the outer
            # ordering controller.
            if pending_budget_exhaustion is not None:
                diagnostic_print(
                    f"Planet Finder {mode}: CONJUNCTION BLOBS EXHAUSTED AFTER CAPS "
                    f"group={group_index + 1} candidates={blob_candidates}; "
                    f"returning cap body={pending_budget_exhaustion.name} "
                    f"to outer controller",
                    flush=True,
                )
                raise pending_budget_exhaustion
            raw_escape_blockers = conjunction_route_diagnostics.get("escape_blocked_by", {})
''',
"deferred cap propagation",
)

TARGET.write_text(text, encoding="utf-8")
print("Conjunction blob recursion now backtracks across downstream body caps.")
