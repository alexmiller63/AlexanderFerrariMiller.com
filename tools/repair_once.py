from pathlib import Path
import subprocess

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

changed = []

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Safety stop: expected exactly one {label}; found {count}")
    return text.replace(old, new, 1)

# 1. Geometry: remove the obsolete invisible anchor-glyph staggering and make
# route() return the actual drawable endpoint, 2 px before the label boundary.
p = Path("tools/planet_finder_geometry.py")
s = p.read_text()
old = '''CONJUNCTION_GLYPH_RADIUS_STEP = 48.0


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
s = replace_once(s, old, "", "obsolete conjunction glyph-radii block")
old = '''        if t_exit < 0.0 or t_enter > 1.0:
            return None
        return source[0] + t_enter * dx, source[1] + t_enter * dy
'''
new = '''        if t_exit < 0.0 or t_enter > 1.0:
            return None
        hit = (source[0] + t_enter * dx, source[1] + t_enter * dy)
        # Return the endpoint that can be rendered directly.  Back off 2 px
        # from the label boundary so the SVG round line cap cannot paint into
        # the label.  Rendering must not recalculate or clip this path later.
        hx, hy = hit[0] - source[0], hit[1] - source[1]
        distance = math.hypot(hx, hy)
        if distance <= 2.0 or distance < 1e-12:
            return source
        scale = (distance - 2.0) / distance
        return source[0] + hx * scale, source[1] + hy * scale
'''
s = replace_once(s, old, new, "target landing return")
p.write_text(s)
changed.append(str(p))

# 2. Search: every astronomical leader anchor is exact lambda at RI-5.  Remove
# all invisible-glyph collision/staggering work and pass each real target box to
# route(), so search owns the final drawable path.
p = Path("tools/planet_finder_search_core.py")
s = p.read_text()
s = replace_once(
    s,
    "    legal_candidate_positions, route, alignment_groups, conjunction_groups, conjunction_glyph_radii,\n",
    "    legal_candidate_positions, route, alignment_groups, conjunction_groups,\n",
    "search import",
)
s = replace_once(
    s,
    '''        w, h = label_size(mode, name)
        glyph_radii = conjunction_glyph_radii(bodies)
        anchor = xy(longitude, glyph_radii.get(name, RI - 5))
''',
    '''        w, h = label_size(mode, name)
        anchor = xy(longitude, RI - 5)
''',
    "ordinary DFS anchor",
)
s = replace_once(
    s,
    '''                allow_initial_escape_count=3,
                prefix_cache=route_prefix_cache,
            )
''',
    '''                allow_initial_escape_count=3,
                prefix_cache=route_prefix_cache,
                target_box=box,
            )
''',
    "ordinary DFS route target",
)
old = '''            # Judge the geometry that will actually be rendered. route()
            # terminates at the label center, but the renderer clips that last
            # segment to the first label-boundary intersection.  No earlier
            # segment may enter or graze the label, and the clipped final
            # approach may touch the label only at its terminating boundary
            # point.  W01 Mixed Saturn exposed a dogleg whose previous segment
            # passed through the label before the nominal final approach.
            def own_label_edge(source):
                dx = source[0] - box.x
                dy = source[1] - box.y
                if abs(dx) < 1e-12 and abs(dy) < 1e-12:
                    return box.x, box.y
                scale = min(
                    box.w / (2.0 * abs(dx)) if abs(dx) >= 1e-12 else float("inf"),
                    box.h / (2.0 * abs(dy)) if abs(dy) >= 1e-12 else float("inf"),
                )
                return box.x + dx * scale, box.y + dy * scale

            rendered_path = [*path[:-1], own_label_edge(path[-2])]
'''
new = '''            # route() now returns the exact drawable path, including the
            # final 2 px label-boundary clearance.  Validate that path directly;
            # do not calculate a second presentation geometry here.
            rendered_path = path
'''
s = replace_once(s, old, new, "duplicate own-label endpoint calculation")
old = '''    # Deterministic conjunction pre-pass.  Conjunction classification fixes
    # exact lambda and radial glyph slots, but it must not freeze an arbitrary
    # label arrangement.  Solve every conjunction as one atomic constraint
    # group, validate the complete group, and only then freeze it.
    by_name = {name: (i, (symbol, name, longitude)) for i, (symbol, name, longitude) in enumerate(bodies)}
    glyph_radii = conjunction_glyph_radii(bodies)
    glyph_radius = 22.0

    def solve_conjunction_group(group, group_index):
        group_items = [by_name[item[1]] for item in group]

        # Exact lambda is observational data.  Only radius changes to separate
        # coincident glyphs; these positions are immutable during label search.
        glyph_centers = {}
        for _, (_, name, longitude) in group_items:
            center = xy(longitude, glyph_radii[name])
            if any(math.hypot(center[0] - other[0], center[1] - other[1]) < 2.0 * glyph_radius
                   for other in glyph_centers.values()):
                raise RuntimeError(
                    f"Planet Finder {mode}: conjunction glyph overlap in group {group_index + 1} at {name}"
                )
            glyph_centers[name] = center
'''
new = '''    # Deterministic conjunction pre-pass.  Anchors are geometric attachment
    # points only: exact lambda at the common RI-5 radius.  The visible glyph is
    # in the displaced label, so no invisible anchor-glyph staggering or glyph
    # collision calculation belongs in the search model.
    by_name = {name: (i, (symbol, name, longitude)) for i, (symbol, name, longitude) in enumerate(bodies)}

    def solve_conjunction_group(group, group_index):
        group_items = [by_name[item[1]] for item in group]
        anchors = {
            name: xy(longitude, RI - 5)
            for _, (_, name, longitude) in group_items
        }
'''
s = replace_once(s, old, new, "conjunction invisible-glyph setup")
s = replace_once(s, "            anchor = glyph_centers[name]\n", "            anchor = anchors[name]\n", "conjunction anchor")
s = replace_once(
    s,
    '''                f"Planet Finder {mode}: SOLVED CONJUNCTION FROZEN body={name} "
                f"lambda={longitude % 360.0:.3f}deg radius={glyph_radii[name]:.1f}",
''',
    '''                f"Planet Finder {mode}: SOLVED CONJUNCTION FROZEN body={name} "
                f"lambda={longitude % 360.0:.3f}deg anchor_radius={RI - 5:.1f}",
''',
    "conjunction diagnostic radius",
)
s = replace_once(
    s,
    '''        anchors = {name: xy(longitude, glyph_radii[name])
                   for name, longitude in longitudes.items()}
''',
    '''        anchors = {name: xy(longitude, RI - 5)
                   for name, longitude in longitudes.items()}
''',
    "alignment anchors",
)
s = replace_once(
    s,
    '''                path = route(
                    anchors[name], (x, y), reserved + placed + other_boxes,
                    allow_initial_escape_count=3,
                )
''',
    '''                path = route(
                    anchors[name], (x, y), reserved + placed + other_boxes,
                    allow_initial_escape_count=3,
                    target_box=chosen[name][2],
                )
''',
    "alignment planned route target",
)
p.write_text(s)
changed.append(str(p))

# 3. Renderer: consume the path selected and validated by search verbatim.
# Remove the obsolete glyph-radii parameter and the second endpoint clipping
# implementation.
p = Path("tools/planet_finder_rendering.py")
s = p.read_text()
s = replace_once(s, "import html\nimport math\n", "import html\n", "renderer math import")
start = s.index("\ndef segment_box_entry(a, b, box):\n")
end = s.index("\ndef render(\n", start)
s = s[:start] + s[end:]
s = replace_once(
    s,
    '''    bodies: list[tuple[str, str, float]],
    glyph_radii: dict[str, float] | None = None,
    budget: dict | None = None,
''',
    '''    bodies: list[tuple[str, str, float]],
    budget: dict | None = None,
''',
    "renderer glyph-radii parameter",
)
s = replace_once(
    s,
    '''    placed = layout(mode, bodies, budget=budget, context_label=context_label)
    if glyph_radii is None:
        glyph_radii = {name: RI - 5 for _, name, _ in bodies}
''',
    '''    placed = layout(mode, bodies, budget=budget, context_label=context_label)
''',
    "renderer unused glyph-radii default",
)
s = replace_once(
    s,
    '''        if year == 2026 and week == 1 and mode == FinderMode.MIXED:
            rendered = rendered_leader(path, box)
            print(
                "PF_TRACE W01 MIXED BODY "
                f"symbol={symbol!r} name={name!r} "
                f"box=center({box.x:.6f},{box.y:.6f}) size({box.w:.6f},{box.h:.6f}) "
                f"search_path={path!r} rendered_path={rendered!r}"
            )
        # Stop just before first contact with this label, even when a dogleg
        # reaches it before the route's nominal final approach.
        out.append(polyline(rendered_leader(path, box)))
''',
    '''        if year == 2026 and week == 1 and mode == FinderMode.MIXED:
            print(
                "PF_TRACE W01 MIXED BODY "
                f"symbol={symbol!r} name={name!r} "
                f"box=center({box.x:.6f},{box.y:.6f}) size({box.w:.6f},{box.h:.6f}) "
                f"path={path!r}"
            )
        # Search returns the authoritative drawable leader geometry.
        out.append(polyline(path))
''',
    "renderer path clipping",
)
p.write_text(s)
changed.append(str(p))

# 4. Generator: stop calculating/passing presentation geometry that no longer
# exists at the anchor.
p = Path("tools/generate_planet_finders.py")
s = p.read_text()
s = replace_once(
    s,
    '''    Box, boxes_overlap, legal_candidate_positions, route, reserved_boxes, RI, CX, CY,
    conjunction_glyph_radii,
)''',
    '''    Box, boxes_overlap, legal_candidate_positions, route, reserved_boxes, RI, CX, CY,
)''',
    "generator glyph-radii import",
)
s = replace_once(
    s,
    '''    # Shared astronomical presentation geometry: compute conjunction glyph
    # displacement once, then give the identical result to every mode.
    glyph_radii = conjunction_glyph_radii(bodies)
''',
    "",
    "generator glyph-radii calculation",
)
s = replace_once(
    s,
    '''        rendered[filename] = render(year, week, monday, mode, bodies, glyph_radii=glyph_radii)
''',
    '''        rendered[filename] = render(year, week, monday, mode, bodies)
''',
    "generator glyph-radii render argument",
)
p.write_text(s)
changed.append(str(p))

# 5. Tests: replace the two obsolete radial-slot tests with assertions for the
# actual architecture: conjunction members share the normal fixed anchor radius.
p = Path("tests/test_planet_finder_conjunctions.py")
s = p.read_text()
s = replace_once(
    s,
    "from planet_finder_geometry import alignment_groups, conjunction_groups, conjunction_glyph_radii\n",
    "from planet_finder_geometry import RI, alignment_groups, conjunction_groups, xy\n",
    "conjunction test import",
)
old = '''def test_level_4_three_body_alignment_gets_three_distinct_radial_slots():
    sky = bodies([("Mercury", 75.0), ("Venus", 75.4), ("Sun", 75.8), ("Mars", 200.0)])
    radii = conjunction_glyph_radii(sky, base_radius=425.0, step=48.0)
    assert len({radii["Mercury"], radii["Venus"], radii["Sun"]}) == 3
    assert radii["Mars"] == 425.0
'''
new = '''def test_level_4_three_body_alignment_keeps_fixed_anchor_radius():
    sky = bodies([("Mercury", 75.0), ("Venus", 75.4), ("Sun", 75.8), ("Mars", 200.0)])
    for _, _, longitude in sky:
        x, y = xy(longitude, RI - 5)
        assert abs(((x - 700.0) ** 2 + (y - 700.0) ** 2) ** 0.5 - (RI - 5)) < 1e-9
'''
s = replace_once(s, old, new, "three-body radial-slot test")
old = '''def test_w2_venus_sun_glyph_slots_are_distinct():
    sky = bodies([("Venus", 284.239), ("Sun", 284.644), ("Mars", 285.759), ("Pluto", 302.840)])
    radii = conjunction_glyph_radii(sky, base_radius=425.0, step=48.0)
    assert radii["Venus"] == 401.0
    assert radii["Sun"] == 449.0
    assert radii["Mars"] == 425.0
    assert radii["Pluto"] == 425.0
'''
new = '''def test_w2_venus_sun_use_same_fixed_anchor_radius():
    sky = bodies([("Venus", 284.239), ("Sun", 284.644), ("Mars", 285.759), ("Pluto", 302.840)])
    for _, _, longitude in sky:
        x, y = xy(longitude, RI - 5)
        assert abs(((x - 700.0) ** 2 + (y - 700.0) ** 2) ** 0.5 - (RI - 5)) < 1e-9
'''
s = replace_once(s, old, new, "W02 radial-slot test")
p.write_text(s)
changed.append(str(p))

# One-shot switch off and commit.
me = Path(__file__)
me.write_text(me.read_text().replace("ENABLED = True", "ENABLED = False", 1))
changed.append(str(me))

subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", *changed], check=True)
subprocess.run(["git", "commit", "-m", "Remove obsolete Planet Finder anchor glyph geometry"], check=True)
subprocess.run(["git", "push", "origin", "HEAD"], check=True)
print("Planet Finder geometry cleanup installed: fixed exact-lambda RI-5 anchors, no invisible anchor-glyph staggering/collision work, search owns final 2 px label landing, renderer draws routed paths verbatim; switch OFF.")
