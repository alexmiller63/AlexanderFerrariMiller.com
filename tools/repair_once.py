from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search.py")
text = path.read_text()

old = '''    def next_promotion_order(current_order, body_name):
        """Return the next bounded ordering for a squeaky-wheel body.

        Try the body at the zero position first, then immediately to its
        right, then at the opposite side of the linearized order.  Relative
        order of every other body is preserved.  This explores the two sides
        of a crowded front position without opening arbitrary permutations.
        """
        body_index = next(
            (i for i, item in enumerate(current_order) if item[1][1] == body_name),
            None,
        )
        if body_index is None:
            return None
        body_item = current_order[body_index]
        rest = [item for i, item in enumerate(current_order) if i != body_index]
        candidate_orders = [
            [body_item, *rest],
            [rest[0], body_item, *rest[1:]],
            [*rest, body_item],
        ]
        for candidate in candidate_orders:
            names = tuple(item[1][1] for item in candidate)
            if (refinement_index, names) not in attempted_orders:
                return candidate
        return None
'''

new = '''    def next_promotion_order(current_order, body_name):
        """Move a blocker left through its local circular-lambda neighborhood.

        The initial order is geometric, so preserve that information.  A body
        that cannot be placed after its immediate predecessors is tried one
        position earlier at a time, allowing DFS to choose the blocker before
        the nearby bodies that constrained it.  This is bounded: once the body
        reaches the front, there is no further promotion for this cycle.
        """
        body_index = next(
            (i for i, item in enumerate(current_order) if item[1][1] == body_name),
            None,
        )
        if body_index is None or body_index == 0:
            return None
        candidate = list(current_order)
        candidate[body_index - 1], candidate[body_index] = (
            candidate[body_index], candidate[body_index - 1]
        )
        names = tuple(item[1][1] for item in candidate)
        if (refinement_index, names) in attempted_orders:
            return None
        return candidate
'''

if text.count(old) != 1:
    raise SystemExit(f"Safety stop: expected promotion function once; found {text.count(old)}")

text = text.replace(old, new, 1)
path.write_text(text)
print("Changed squeaky-wheel promotion to one-step local lambda promotion.")
