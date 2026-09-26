from planet_finder_geometry import alignment_groups, conjunction_groups, conjunction_glyph_radii


def names(groups):
    return [[item[1] for item in group] for group in groups]


def bodies(longitudes):
    return [(name.lower(), name, longitude) for name, longitude in longitudes]


# Level 0: trivial, widely separated geometry.
def test_level_0_one_body_has_no_alignment():
    assert conjunction_groups(bodies([("Sun", 10.0)])) == []


def test_level_0_widely_separated_bodies_have_no_alignments():
    sky = bodies([("Sun", 0.0), ("Mercury", 60.0), ("Venus", 120.0), ("Mars", 180.0), ("Jupiter", 240.0), ("Saturn", 300.0)])
    assert conjunction_groups(sky) == []


# Level 1: a full ordinary system, still deliberately uncrowded.
def test_level_1_full_system_has_no_alignments():
    names12 = ["Sun", "Mercury", "Venus", "Earth", "Moon", "Mars", "Ceres", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
    sky = bodies([(name, i * 30.0) for i, name in enumerate(names12)])
    assert conjunction_groups(sky) == []


# Level 2: exactly one alignment; everything else is separate.
def test_level_2_one_alignment_resolves_in_lambda_order():
    sky = bodies([("Sun", 100.4), ("Venus", 100.0), ("Mars", 180.0), ("Jupiter", 260.0)])
    assert names(conjunction_groups(sky)) == [["Venus", "Sun"]]


# Level 3: two independent alignments.
def test_level_3_two_alignments_are_independent_and_ordered():
    sky = bodies([("Sun", 40.4), ("Venus", 40.0), ("Mars", 210.0), ("Pluto", 210.5), ("Jupiter", 300.0)])
    assert names(conjunction_groups(sky)) == [["Venus", "Sun"], ["Mars", "Pluto"]]


# Level 4: three bodies in one alignment.
def test_level_4_three_body_alignment_is_lambda_ordered():
    sky = bodies([("Mercury", 75.0), ("Venus", 75.4), ("Sun", 75.8), ("Mars", 200.0)])
    assert names(conjunction_groups(sky)) == [["Mercury", "Venus", "Sun"]]


def test_level_4_three_body_alignment_gets_three_distinct_radial_slots():
    sky = bodies([("Mercury", 75.0), ("Venus", 75.4), ("Sun", 75.8), ("Mars", 200.0)])
    radii = conjunction_glyph_radii(sky, base_radius=425.0, step=48.0)
    assert len({radii["Mercury"], radii["Venus"], radii["Sun"]}) == 3
    assert radii["Mars"] == 425.0


# Geometry edge case: an alignment crossing lambda=0 still orders circularly.
def test_alignment_wraps_across_zero_degrees():
    sky = bodies([("A", 359.8), ("B", 0.2), ("C", 40.0)])
    assert names(conjunction_groups(sky)) == [["A", "B"]]


# Real W2 regression facts already isolated from the workflow diagnostic.
def test_w2_venus_sun_is_alignment_and_mars_pluto_is_not():
    sky = bodies([("Venus", 284.239), ("Sun", 284.644), ("Mars", 285.759), ("Pluto", 302.840)])
    groups = names(conjunction_groups(sky))
    assert ["Venus", "Sun"] in groups
    assert not any("Mars" in group and "Pluto" in group for group in groups)


def test_w2_venus_sun_glyph_slots_are_distinct():
    sky = bodies([("Venus", 284.239), ("Sun", 284.644), ("Mars", 285.759), ("Pluto", 302.840)])
    radii = conjunction_glyph_radii(sky, base_radius=425.0, step=48.0)
    assert radii["Venus"] == 401.0
    assert radii["Sun"] == 449.0
    assert radii["Mars"] == 425.0
    assert radii["Pluto"] == 425.0


# Broad alignment classification (<=30 degrees), separate from <=1 degree conjunctions.
def test_alignment_classifier_widely_separated_bodies_are_independent():
    sky = bodies([("Sun", 0.0), ("Mercury", 60.0), ("Venus", 120.0), ("Mars", 180.0)])
    assert alignment_groups(sky) == []


def test_alignment_classifier_one_broad_alignment():
    sky = bodies([("Sun", 10.0), ("Venus", 25.0), ("Mars", 100.0)])
    assert names(alignment_groups(sky)) == [["Sun", "Venus"]]


def test_alignment_classifier_two_independent_alignments():
    sky = bodies([("Sun", 10.0), ("Venus", 25.0), ("Mars", 160.0), ("Jupiter", 180.0)])
    assert names(alignment_groups(sky)) == [["Sun", "Venus"], ["Mars", "Jupiter"]]


def test_alignment_classifier_excludes_frozen_conjunction_members():
    sky = bodies([("Venus", 10.0), ("Sun", 10.4), ("Mars", 20.0), ("Jupiter", 100.0)])
    assert names(conjunction_groups(sky)) == [["Venus", "Sun"]]
    assert alignment_groups(sky) == []


def test_alignment_classifier_wraps_across_zero():
    sky = bodies([("A", 350.0), ("B", 10.0), ("C", 100.0)])
    assert names(alignment_groups(sky)) == [["A", "B"]]


def test_w1_sun_venus_is_broad_alignment_not_conjunction():
    sky = bodies([("Venus", 0.0), ("Sun", 2.081), ("Mars", 100.0)])
    assert conjunction_groups(sky) == []
    assert names(alignment_groups(sky)) == [["Venus", "Sun"]]
