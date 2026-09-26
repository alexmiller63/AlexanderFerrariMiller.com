from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search.py")
text = path.read_text()

old_state = '''    attempted_orders = set()
    # Exhausted searches use this to bound squeaky-wheel promotion cycles.
    # CAPPED searches instead use attempted_orders to exhaust the three
    # explicitly bounded positions for that body before refinement.
    promoted_bodies = set()
    # One per-body candidate cap for the current placement refinement.
'''
new_state = '''    attempted_orders = set()
    # One per-body candidate cap for the current placement refinement.
'''

old_refine_clear = '''            attempted_orders.clear()
            promoted_bodies.clear()
            for name in body_attempts:
'''
new_refine_clear = '''            attempted_orders.clear()
            for name in body_attempts:
'''

old_repeat = '''        if order_key in attempted_orders:
            state = "REFINE"
            continue
'''
new_repeat = '''        if order_key in attempted_orders:
            raise RuntimeError(
                f"Planet Finder {mode}: controller invariant violated: "
                "repeated an ordering before sticky promotion reached position 0; "
                f"refinement={refinement_scales[refinement_index]:g} "
                f"sequence={' > '.join(order_names)}"
            )
'''

for label, old in (
    ("obsolete promotion state", old_state),
    ("obsolete promotion reset", old_refine_clear),
    ("repeat-order refinement escape", old_repeat),
):
    if text.count(old) != 1:
        raise SystemExit(f"Safety stop: expected {label} once; found {text.count(old)}")

text = text.replace(old_state, new_state, 1)
text = text.replace(old_refine_clear, new_refine_clear, 1)
text = text.replace(old_repeat, new_repeat, 1)

if "promoted_bodies" in text:
    raise SystemExit("Safety stop: promoted_bodies still remains")

path.write_text(text)
print("Removed obsolete promotion state and enforced sticky-promotion-only refinement.")
