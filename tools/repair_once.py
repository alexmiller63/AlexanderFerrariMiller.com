from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_geometry.py")
text = path.read_text()
old = "CONJUNCTION_GLYPH_RADIUS_STEP = 34.0"
new = "CONJUNCTION_GLYPH_RADIUS_STEP = 48.0"
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: expected conjunction glyph step once; found {text.count(old)}")
path.write_text(text.replace(old, new, 1))

# Keep the unit test synchronized with the production default and verify the
# two glyph circles have positive clearance at the W2-like separation.
path = Path("tests/test_planet_finder_conjunctions.py")
text = path.read_text()
text = text.replace(
    'radii = conjunction_glyph_radii(bodies, base_radius=425.0, step=34.0)',
    'radii = conjunction_glyph_radii(bodies, base_radius=425.0, step=48.0)',
    1,
)
text = text.replace('assert radii["Venus"] == 408.0', 'assert radii["Venus"] == 401.0', 1)
text = text.replace('assert radii["Sun"] == 442.0', 'assert radii["Sun"] == 449.0', 1)
path.write_text(text)

print("Conjunction glyph radial spacing set to 48 px.")
