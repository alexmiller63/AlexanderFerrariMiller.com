from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

# Step 1: add shared, mode-independent conjunction glyph radii.
path = Path("tools/planet_finder_geometry.py")
text = path.read_text()
needle = '''def conjunction_groups(bodies, threshold: float = NEAR_CONJUNCTION_DEGREES):'''
if text.count(needle) != 1:
    raise SystemExit(f"Safety stop: conjunction_groups count={text.count(needle)}")

insert_before = needle
addition = '''CONJUNCTION_GLYPH_RADIUS_STEP = 34.0


def conjunction_glyph_radii(bodies, base_radius: float = RI - 5, step: float = CONJUNCTION_GLYPH_RADIUS_STEP):
    """Return per-body glyph radii shared by every presentation mode.

    Ordinary bodies remain at base_radius.  Members of each near-conjunction
    group are already in circular lambda order; assign distinct radial slots in
    that same order so no recursive search is needed to separate their glyphs.
    """
    radii = {item[1]: base_radius for item in bodies}
    for group in conjunction_groups(bodies):
        n = len(group)
        center = (n - 1) / 2.0
        for i, item in enumerate(group):
            radii[item[1]] = base_radius + (i - center) * step
    return radii


'''
text = text.replace(insert_before, addition + insert_before, 1)
path.write_text(text)

# Step 2: compute this geometry once per week, before the mode loop.
path = Path("tools/generate_planet_finders.py")
text = path.read_text()
old_import = '''    Box, boxes_overlap, legal_candidate_positions, route, reserved_boxes, RI, CX, CY,
)'''
new_import = '''    Box, boxes_overlap, legal_candidate_positions, route, reserved_boxes, RI, CX, CY,
    conjunction_glyph_radii,
)'''
if text.count(old_import) != 1:
    raise SystemExit(f"Safety stop: generator import point count={text.count(old_import)}")
text = text.replace(old_import, new_import, 1)
old = '''    bodies = [(BODY_SYMBOLS[BODY_NAMES[name]], name, values[BODY_NAMES[name]] % 360) for name in CANONICAL]
    outdir = week_dir(year, week) / "finders"'''
new = '''    bodies = [(BODY_SYMBOLS[BODY_NAMES[name]], name, values[BODY_NAMES[name]] % 360) for name in CANONICAL]
    # Shared astronomical presentation geometry: compute conjunction glyph
    # displacement once, then give the identical result to every mode.
    glyph_radii = conjunction_glyph_radii(bodies)
    outdir = week_dir(year, week) / "finders"'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: bodies point count={text.count(old)}")
text = text.replace(old, new, 1)
old = '''        rendered[filename] = render(year, week, monday, mode, bodies)'''
new = '''        rendered[filename] = render(year, week, monday, mode, bodies, glyph_radii=glyph_radii)'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: render call count={text.count(old)}")
text = text.replace(old, new, 1)
path.write_text(text)

# Step 3: render a distinct glyph at true lambda with the shared radial slot.
# Existing labels and recursive routing remain untouched for this wiring step.
path = Path("tools/planet_finder_rendering.py")
text = path.read_text()
old = '''    bodies: list[tuple[str, str, float]],
    budget: dict | None = None,'''
new = '''    bodies: list[tuple[str, str, float]],
    glyph_radii: dict[str, float] | None = None,
    budget: dict | None = None,'''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: render signature count={text.count(old)}")
text = text.replace(old, new, 1)
old = '''    title = labels[mode]
    placed = layout(mode, bodies, budget=budget, context_label=context_label)
    out = ['''
new = '''    title = labels[mode]
    placed = layout(mode, bodies, budget=budget, context_label=context_label)
    if glyph_radii is None:
        glyph_radii = {name: RI - 5 for _, name, _ in bodies}
    out = ['''
if text.count(old) != 1:
    raise SystemExit(f"Safety stop: render setup count={text.count(old)}")
text = text.replace(old, new, 1)
marker = '''    for symbol, name, _, box, path in placed:
'''
addition = '''    # Body glyphs are a separate astronomical layer.  Longitude is never
    # altered; only radius changes for deterministic near-conjunction spacing.
    for symbol, name, longitude in bodies:
        gx, gy = xy(longitude, glyph_radii[name])
        out.append(f'<circle cx="{gx:.1f}" cy="{gy:.1f}" r="22" fill="white" stroke="#111" stroke-width="1.5"/>')
        out.append(f'<text x="{gx:.1f}" y="{gy+10:.1f}" text-anchor="middle" font-size="32">{html.escape(symbol)}\\ufe0e</text>')

'''
if text.count(marker) != 1:
    raise SystemExit(f"Safety stop: placed marker count={text.count(marker)}")
text = text.replace(marker, addition + marker, 1)
path.write_text(text)

# Step 4: strengthen the unit contract for deterministic radial assignment.
path = Path("tests/test_planet_finder_conjunctions.py")
text = path.read_text()
text = text.replace(
    'from planet_finder_geometry import conjunction_groups',
    'from planet_finder_geometry import conjunction_groups, conjunction_glyph_radii',
    1,
)
text += '''\n\ndef test_conjunction_glyph_radii_follow_lambda_order():\n    bodies = [("sun", "Sun", 284.644), ("venus", "Venus", 284.239), ("mars", "Mars", 10.0)]\n    radii = conjunction_glyph_radii(bodies, base_radius=425.0, step=34.0)\n    assert radii["Venus"] == 408.0\n    assert radii["Sun"] == 442.0\n    assert radii["Mars"] == 425.0\n'''
path.write_text(text)

print("Wired shared conjunction glyph geometry into all Planet Finder modes.")
