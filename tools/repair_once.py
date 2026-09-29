#!/usr/bin/env python3
"""One-shot repair: make conjunctions use ordinary placement as an atomic blob."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

start_marker = "    def solve_conjunction_group(group, group_index, downstream):\n"
end_marker = "    conjunction_group_list = conjunction_groups(bodies)\n"

if text.count(start_marker) != 1 or text.count(end_marker) != 1:
    raise SystemExit(
        "Safety stop: expected exactly one conjunction solver and one conjunction-list marker"
    )

start = text.index(start_marker)
end = text.index(end_marker, start)

new = '''    def solve_conjunction_group(group, group_index, downstream):
        """Solve a conjunction with ordinary geometry, but backtrack it atomically.

        Crossing the conjunction threshold changes only the unit of recursion:
        every member is placed by viable_candidates(), exactly like an ordinary
        body.  A complete group is then handed downstream as one transaction;
        downstream failure restores/backtracks the whole group and tries the
        next ordinary candidate combination.
        """
        group_items = [by_name[item[1]] for item in group]
        ordered_names = [item[1][1] for item in group_items]
        blob_candidates = 0
        downstream_rejections = 0
        pending_budget_exhaustion = None

        def assign(depth):
            nonlocal blob_candidates, downstream_rejections
            nonlocal pending_budget_exhaustion

            if depth == len(group_items):
                blob_candidates += 1
                diagnostic_print(
                    f"Planet Finder {mode}: CONJUNCTION BLOB ORDINARY-GEOMETRY "
                    f"group={group_index + 1} candidate={blob_candidates} "
                    f"bodies={' > '.join(ordered_names)}",
                    flush=True,
                )

                # Downstream search belongs to this complete blob candidate.
                # If it fails, restore its body budgets before trying the next
                # conjunction arrangement so sibling blobs are independent.
                body_attempts_before = dict(body_attempts)
                try:
                    if downstream():
                        return True
                except DepthNodeBudgetExhausted as exc:
                    if pending_budget_exhaustion is None:
                        pending_budget_exhaustion = exc
                finally:
                    body_attempts.clear()
                    body_attempts.update(body_attempts_before)

                downstream_rejections += 1
                return False

            item = group_items[depth]
            original_index, (symbol, name, longitude) = item

            # This is deliberately the SAME candidate generator used by the
            # ordinary DFS.  No conjunction-only pool, displacement scale,
            # lambda gate, routing rule, or collision rule belongs here.
            for box, path in viable_candidates(
                    item, depth, consume_body_budget=False):
                placed.append(box)
                leaders.append(path)
                leader_names.append(name)
                staged[original_index] = (symbol, name, longitude, box, path)

                if assign(depth + 1):
                    return True

                staged.pop(original_index, None)
                leader_names.pop()
                leaders.pop()
                placed.pop()

            return False

        solved = assign(0)
        if solved:
            return True

        diagnostic_print(
            f"Planet Finder {mode}: CONJUNCTION ORDINARY-GEOMETRY EXHAUSTED "
            f"group={group_index + 1} bodies={' > '.join(ordered_names)} "
            f"blob_candidates={blob_candidates} "
            f"downstream_rejections={downstream_rejections}",
            flush=True,
        )
        if pending_budget_exhaustion is not None:
            raise pending_budget_exhaustion
        return False

'''

text = text[:start] + new + text[end:]
TARGET.write_text(text, encoding="utf-8")

# Self-disarm after the successful one-shot rewrite.
me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Replaced the special conjunction placement algorithm with the ordinary "
    "viable-candidate solver wrapped in atomic conjunction backtracking. "
    "The 1-degree threshold now changes grouping only, not placement geometry. "
    "Repair Once is now OFF."
)
