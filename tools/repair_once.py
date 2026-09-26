from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search.py")
text = path.read_text()

old_comment = '''    # Explicit search-controller state machine. Search attempts report events;
    # only the controller changes ordering or placement refinement.
    #
    # SEARCH_ORDER -> SCORE    on SOLVED
    # SEARCH_ORDER -> CAPPED   on CAPPED(body)
    # SEARCH_ORDER -> PROMOTE  on EXHAUSTED(blocker)
    # CAPPED       -> SEARCH_ORDER while another bounded sideways position exists
    # CAPPED       -> REFINE when all three bounded positions are exhausted
    # PROMOTE      -> SEARCH_ORDER when the exhausted blocker ordering is new
    # PROMOTE      -> REFINE   when EXHAUSTED promotion closes an ordering cycle
    # REFINE       -> SEARCH_ORDER at the next placement scale
'''
new_comment = '''    # Explicit search-controller state machine. Search attempts report facts;
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
'''

old_capped = '''        if state == "CAPPED":
            # A node cap is incomplete evidence. Exhaust the three explicitly
            # bounded positions for this body (front, one step right, far side)
            # before allowing the controller to change placement refinement.
            promoted_order = next_promotion_order(order, promote_body)
            if promoted_order is None:
                cycle_names = " > ".join(item[1][1] for item in order)
                diagnostic_print(
                    f"Planet Finder {mode}: CAPPED SIDEWAYS CYCLE CLOSED body={promote_body}; "
                    f"orderings={len(attempted_orders)} "
                    f"at {refinement_scales[refinement_index]:g} label-lengths "
                    f"sequence={cycle_names}; refining",
                    flush=True,
                )
                state = "REFINE"
                continue
            promoted_names = tuple(item[1][1] for item in promoted_order)
            # Each bounded ordering gets a fresh 200-candidate budget for the
            # capped body. Forward checking remains outside this accounting.
            body_attempts[promote_body] = 0
            order = promoted_order
            diagnostic_print(
                f"Planet Finder {mode}: CAPPED SIDEWAYS body={promote_body}; "
                f"reset candidate budget to 0/{budget['max_node_candidates']:,}; "
                "trying next bounded position sequence="
                + " > ".join(promoted_names),
                flush=True,
            )
            state = "SEARCH_ORDER"
            continue

'''

old_sticky_assignment = '''        promote_body = outcome.blocker
        if sticky_promote_body is not None and outcome.kind == "EXHAUSTED":
            promote_body = sticky_promote_body
'''
new_sticky_assignment = '''        # Once promotion starts, the selected blocker remains sticky regardless
        # of whether a subsequent fixed-order attempt reports CAPPED or
        # EXHAUSTED for another body.  Finish learning this body's ordering
        # before changing refinement or selecting another blocker.
        if sticky_promote_body is None:
            sticky_promote_body = outcome.blocker
        promote_body = sticky_promote_body
'''

old_transition = '''        # EXHAUSTED is proof about the complete fixed-order search and may
        # participate in the refinement state machine. CAPPED is only a safety
        # interruption and gets its own non-refining transition.
        state = "CAPPED" if outcome.kind == "CAPPED" else "PROMOTE"
'''
new_transition = '''        # CAPPED and EXHAUSTED are different diagnostic facts, but both mean
        # this fixed ordering did not produce the requested contest.  Ordering
        # policy is unified: both enter the same sticky promotion state.
        state = "PROMOTE"
'''

for label, old in (
    ("state-machine comment", old_comment),
    ("legacy CAPPED controller", old_capped),
    ("sticky blocker assignment", old_sticky_assignment),
    ("split outcome transition", old_transition),
):
    if text.count(old) != 1:
        raise SystemExit(f"Safety stop: expected {label} once; found {text.count(old)}")

text = text.replace(old_comment, new_comment, 1)
text = text.replace(old_capped, "", 1)
text = text.replace(old_sticky_assignment, new_sticky_assignment, 1)
text = text.replace(old_transition, new_transition, 1)

# No controller state named CAPPED should remain after this architectural cleanup.
if 'state == "CAPPED"' in text or 'state = "CAPPED"' in text:
    raise SystemExit("Safety stop: legacy CAPPED controller state remains")

path.write_text(text)
print("Unified CAPPED and EXHAUSTED under one sticky blocker-promotion policy.")
