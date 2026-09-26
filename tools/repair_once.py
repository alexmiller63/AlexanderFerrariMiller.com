from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_rendering.py")
text = path.read_text()

old = '''    for symbol, name, _, box, path in placed:
        # route() deliberately ends at the label center. Clip that final
'''

new = '''    for symbol, name, _, box, path in placed:
        if year == 2026 and week == 1 and mode == FinderMode.MIXED and name == "Saturn":
            rendered = rendered_leader(path, box)
            print(
                "PF_TRACE W01 MIXED SATURN "
                f"box=center({box.x:.6f},{box.y:.6f}) size({box.w:.6f},{box.h:.6f}) "
                f"search_path={path!r} rendered_path={rendered!r}"
            )
        # route() deliberately ends at the label center. Clip that final
'''

if text.count(old) != 1:
    raise SystemExit(
        f"Safety stop: expected rendering loop once; found {text.count(old)}"
    )

path.write_text(text.replace(old, new, 1))
print("W01 Mixed Saturn rendering trace is armed.")
