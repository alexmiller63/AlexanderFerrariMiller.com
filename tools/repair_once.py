from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search.py")
text = path.read_text()

old_state = '''    # Explicit search-controller state machine. Search attempts report facts;
    # only the controller changes ordering or placement refinement.
    #
    # SEARCH_ORDER -> SCORE    on SOLVED
    # SEARCH_ORDER -> PROMOTE  on BLOCKED(body), whether CAPPED or EXHAUSTED
    # PROMOTE      -> SEARCH_ORDER after moving the sticky blocker left one step
    # PROMOTE      -> REFINE   when that blocker has reached position 0
    # REFINE       -> SEARCH_ORDER at the next placement scale
    #
    # CAPPED versus EXHAUSTED remains diagnostic information only.  It does
    # not select a second reordering policy.
    state = "SEARCH_ORDER"
    promote_body = None
    sticky_promote_body = None
'''
new_state = '''    # Explicit search-controller state machine. Search attempts report facts;
    # only the controller changes ordering or placement refinement.
    #
    # SEARCH_ORDER -> SCORE    on SOLVED
    # SEARCH_ORDER -> PROMOTE  on BLOCKED(body), whether CAPPED or EXHAUSTED
    # PROMOTE      -> SEARCH_ORDER after moving the current blocker left one step
    # PROMOTE      -> REFINE   only when the current blocker is already position 0
    # REFINE       -> SEARCH_ORDER at the next placement scale
    #
    # CAPPED versus EXHAUSTED remains diagnostic information only.  It does
    # not select a second reordering policy.
    state = "SEARCH_ORDER"
    promote_body = None
'''

old_helper = '''    def next_promotion_order(current_order, body_name):
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
new_helper = '''    def next_promotion_order(current_order, body_name):
        """Return an explicit transition for promoting the current blocker.

        ``AT_FRONT`` is the only transition that permits refinement.  A
        previously attempted candidate is a controller cycle, not successful
        completion of promotion, and is reported separately.
        """
        body_index = next(
            (i for i, item in enumerate(current_order) if item[1][1] == body_name),
            None,
        )
        if body_index is None:
            return "MISSING", None
        if body_index == 0:
            return "AT_FRONT", None
        candidate = list(current_order)
        candidate[body_index - 1], candidate[body_index] = (
            candidate[body_index], candidate[body_index - 1]
        )
        names = tuple(item[1][1] for item in candidate)
        if (refinement_index, names) in attempted_orders:
            return "CYCLE", candidate
        return "PROMOTE", candidate
'''

old_reset = '''            promote_body = None
            sticky_promote_body = None
'''
new_reset = '''            promote_body = None
'''

old_promote = '''        if state == "PROMOTE":
            # Promotion is sticky within a refinement.  Once a blocker starts
            # moving left through the lambda order, keep moving that same body
            # one neighbor at a time.  A newly exposed blocker must not undo
            # the ordering knowledge we just learned.
            if sticky_promote_body is None:
                sticky_promote_body = promote_body
            promoted_order = next_promotion_order(order, sticky_promote_body)
            if promoted_order is None:
                diagnostic_print(
                    f"Planet Finder {mode}: STICKY PROMOTION COMPLETE body={sticky_promote_body} "
                    f"at position 0; refinement={refinement_scales[refinement_index]:g} "
                    "label-lengths; refining",
                    flush=True,
                )
                sticky_promote_body = None
                state = "REFINE"
            else:
                promoted_names = tuple(item[1][1] for item in promoted_order)
                order = promoted_order
                body_attempts[sticky_promote_body] = 0
                diagnostic_print(
                    f"Planet Finder {mode}: STICKY PROMOTE body={sticky_promote_body}; "
                    "moved left one lambda neighbor; restarting sequence="
                    + " > ".join(promoted_names),
                    flush=True,
                )
                state = "SEARCH_ORDER"
            continue
'''
new_promote = '''        if state == "PROMOTE":
            transition, promoted_order = next_promotion_order(order, promote_body)
            if transition == "AT_FRONT":
                diagnostic_print(
                    f"Planet Finder {mode}: PROMOTION COMPLETE body={promote_body} "
                    f"at position 0; refinement={refinement_scales[refinement_index]:g} "
                    "label-lengths; refining",
                    flush=True,
                )
                promote_body = None
                state = "REFINE"
            elif transition == "PROMOTE":
                promoted_names = tuple(item[1][1] for item in promoted_order)
                order = promoted_order
                body_attempts[promote_body] = 0
                diagnostic_print(
                    f"Planet Finder {mode}: PROMOTE body={promote_body}; "
                    "moved left one lambda neighbor; restarting sequence="
                    + " > ".join(promoted_names),
                    flush=True,
                )
                state = "SEARCH_ORDER"
            elif transition == "CYCLE":
                cycle_names = tuple(item[1][1] for item in promoted_order)
                raise RuntimeError(
                    f"Planet Finder {mode}: controller cycle detected while promoting "
                    f"{promote_body}; refinement={refinement_scales[refinement_index]:g} "
                    f"candidate={' > '.join(cycle_names)}"
                )
            else:
                raise RuntimeError(
                    f"Planet Finder {mode}: controller invariant violated: blocker "
                    f"{promote_body!r} is absent from the recursive search order"
                )
            continue
'''

old_outcome = '''        # Once promotion starts, the selected blocker remains sticky regardless
        # of whether a subsequent fixed-order attempt reports CAPPED or
        # EXHAUSTED for another body.  Finish learning this body's ordering
        # before changing refinement or selecting another blocker.
        sticky_promote_body = outcome.blocker
        promote_body = outcome.blocker
'''
new_outcome = '''        # Squeaky-wheel feedback: each failed search names the blocker for the
        # next single promotion step.  The next search may identify a different
        # blocker; no blocker remains sticky across searches.
        promote_body = outcome.blocker
'''

replacements = [
    (old_state, new_state, "state declaration"),
    (old_helper, new_helper, "promotion transition helper"),
    (old_reset, new_reset, "refinement reset"),
    (old_promote, new_promote, "PROMOTE state"),
    (old_outcome, new_outcome, "search outcome transition"),
]
for old, new, label in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Safety stop: expected {label} exactly once; found {count}")
    text = text.replace(old, new, 1)

path.write_text(text)
print("Refactored Planet Finder controller to explicit current-blocker transitions.")
