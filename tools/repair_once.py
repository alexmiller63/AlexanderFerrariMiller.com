from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search.py")
text = path.read_text()

old_deadlines = '''    # Keep one wall clock per notation mode, but reserve an equal cumulative
    # share for each refinement so a coarse geometry cannot consume time that
    # belongs to the finer fallback geometries.
    refinement_deadlines = tuple(
        budget["started"] + budget["max_seconds"] * (i + 1) / len(refinement_scales)
        for i in range(len(refinement_scales))
    )
'''

old_slice_guard = '''        if state != "REFINE" and now >= refinement_deadlines[refinement_index]:
            if refinement_index + 1 >= len(refinement_scales):
                raise RuntimeError(
                    f"Planet Finder {mode} mode wall-clock budget exhausted "
                    f"(limit {budget['max_seconds']:.1f}s)"
                )
            diagnostic_print(
                f"Planet Finder {mode}: REFINEMENT TIME SLICE EXHAUSTED "
                f"at {refinement_scales[refinement_index]:g} label-lengths; "
                f"elapsed={now - budget['started']:.1f}s; advancing",
                flush=True,
            )
            state = "REFINE"
            continue

'''

old_solver_arg = '''                body_attempts=body_attempts,
                refinement_deadline=refinement_deadlines[refinement_index],
'''
new_solver_arg = '''                body_attempts=body_attempts,
                refinement_deadline=budget["started"] + budget["max_seconds"],
'''

for label, old in (
    ("refinement deadline allocation", old_deadlines),
    ("refinement time-slice guard", old_slice_guard),
    ("solver refinement deadline argument", old_solver_arg),
):
    if text.count(old) != 1:
        raise SystemExit(f"Safety stop: expected {label} once; found {text.count(old)}")

text = text.replace(old_deadlines, "", 1)
text = text.replace(old_slice_guard, "", 1)
text = text.replace(old_solver_arg, new_solver_arg, 1)
path.write_text(text)
print("Removed per-refinement time slices; all searches now share the single mode clock.")
