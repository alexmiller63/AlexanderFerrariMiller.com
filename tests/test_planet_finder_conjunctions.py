from planet_finder_geometry import conjunction_groups


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
