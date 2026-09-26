from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/populate_ephemeris_planet_finder_by_date.py")
text = path.read_text()

old = '''    bodies = finder_bodies(generated, week)
    # The week is the publication unit. Keep finder assets beneath the week
'''

new = '''    bodies = finder_bodies(generated, week)
    # Diagnostic fixture capture: print the exact production inputs so any
    # real-week failure can be reproduced by a deterministic regression test
    # without depending on the ephemeris engine.
    print(
        "PLANET_FINDER_FIXTURE "
        + context_label
        + " "
        + repr({name: longitude for _, name, longitude in bodies}),
        flush=True,
    )
    # The week is the publication unit. Keep finder assets beneath the week
'''

if text.count(old) != 1:
    raise SystemExit(f"Safety stop: expected finder_bodies call once; found {text.count(old)}")

path.write_text(text.replace(old, new, 1))
print("Planet Finder weekly build now emits exact 11-body longitude fixture before search.")
