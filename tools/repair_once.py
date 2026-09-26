from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search.py")
text = path.read_text()
old = '''            elif transition == "CYCLE":
                cycle_names = tuple(item[1][1] for item in promoted_order)
                raise RuntimeError(
                    f"Planet Finder {mode}: controller cycle detected while promoting "
                    f"{promote_body}; refinement={refinement_scales[refinement_index]:g} "
                    f"candidate={' > '.join(cycle_names)}"
                )
'''
new = '''            elif transition == "CYCLE":
                cycle_names = tuple(item[1][1] for item in promoted_order)
                diagnostic_print(
                    f"Planet Finder {mode}: ORDERING CYCLE EXHAUSTED while promoting "
                    f"{promote_body}; refinement={refinement_scales[refinement_index]:g} "
                    f"candidate={' > '.join(cycle_names)}; refining",
                    flush=True,
                )
                promote_body = None
                state = "REFINE"
'''

if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: expected controller-cycle transition exactly once; found {text.count(old)}"
    )

path.write_text(text.replace(old, new, 1))
print("Changed controller cycle transition from error to refinement.")
