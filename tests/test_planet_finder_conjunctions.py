from planet_finder_geometry import conjunction_groups, conjunction_glyph_radii


def names(groups):
    return [[item[1] for item in group] for group in groups]


def test_near_conjunction_members_resolve_in_lambda_order():
    bodies = [("sun", "Sun", 284.644), ("venus", "Venus", 284.239), ("mars", "Mars", 10.0)]
    assert names(conjunction_groups(bodies)) == [["Venus", "Sun"]]


def test_near_conjunction_wraps_across_zero_degrees():
    bodies = [("a", "A", 359.8), ("b", "B", 0.2), ("c", "C", 40.0)]
    assert names(conjunction_groups(bodies)) == [["A", "B"]]


def test_separate_bodies_are_not_groups():
    bodies = [("a", "A", 10.0), ("b", "B", 20.0), ("c", "C", 30.0)]
    assert conjunction_groups(bodies) == []


def test_conjunction_glyph_radii_follow_lambda_order():
    bodies = [("sun", "Sun", 284.644), ("venus", "Venus", 284.239), ("mars", "Mars", 10.0)]
    radii = conjunction_glyph_radii(bodies, base_radius=425.0, step=34.0)
    assert radii["Venus"] == 408.0
    assert radii["Sun"] == 442.0
    assert radii["Mars"] == 425.0
