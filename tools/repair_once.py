from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search.py")
text = path.read_text()

old_init = '''    state = "SEARCH_ORDER"
    promote_body = None
'''
new_init = '''    state = "SEARCH_ORDER"
    promote_body = None
    sticky_promote_body = None
'''

old_promote = '''        if state == "PROMOTE":
            if promote_body in promoted_bodies:
                diagnostic_print(
                    f"Planet Finder {mode}: PROMOTION REPEAT body={promote_body}; "
                    f"promoted={len(promoted_bodies)}/{len(indexed)} "
                    f"at {refinement_scales[refinement_index]:g} label-lengths; refining",
                    flush=True,
                )
                state = "REFINE"
                continue
            promoted_bodies.add(promote_body)
            promoted_order = next_promotion_order(order, promote_body)
            if promoted_order is None:
                diagnostic_print(
                    f"Planet Finder {mode}: PROMOTION SIDEWAYS CYCLE CLOSED body={promote_body} "
                    f"at {refinement_scales[refinement_index]:g} label-lengths; refining",
                    flush=True,
                )
                state = "REFINE"
            else:
                promoted_names = tuple(item[1][1] for item in promoted_order)
                order = promoted_order
                diagnostic_print(
                    f"Planet Finder {mode}: PROMOTE/SIDEWAYS body={promote_body}; "
                    "discarding fixed-order search state and restarting with sequence="
                    + " > ".join(promoted_names),
                    flush=True,
                )
                state = "SEARCH_ORDER"
            continue
'''

new_promote = '''        if state == "PROMOTE":
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

old_assignment = '''        promote_body = outcome.blocker
        refinement_history.append({
'''
new_assignment = '''        promote_body = outcome.blocker
        if sticky_promote_body is not None and outcome.kind == "EXHAUSTED":
            promote_body = sticky_promote_body
        refinement_history.append({
'''

old_refine_reset = '''            promote_body = None
            diagnostic_print(
'''
new_refine_reset = '''            promote_body = None
            sticky_promote_body = None
            diagnostic_print(
'''

for label, old in (("controller init", old_init), ("PROMOTE state", old_promote), ("outcome assignment", old_assignment), ("refinement reset", old_refine_reset)):
    if text.count(old) != 1:
        raise SystemExit(f"Safety stop: expected {label} once; found {text.count(old)}")

text = text.replace(old_init, new_init, 1)
text = text.replace(old_promote, new_promote, 1)
text = text.replace(old_assignment, new_assignment, 1)
text = text.replace(old_refine_reset, new_refine_reset, 1)
path.write_text(text)
print("Installed sticky one-neighbor lambda promotion before refinement.")
