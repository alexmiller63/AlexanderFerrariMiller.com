from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_geometry.py")
text = path.read_text()

needle = '''DEFAULT_MAX_SEARCH_SECONDS = 180


class FinderMode'''
replacement = '''DEFAULT_MAX_SEARCH_SECONDS = 180

# Bodies closer than this in ecliptic longitude form one deterministic
# near-conjunction group before any presentation-mode search begins.
NEAR_CONJUNCTION_DEGREES = 1.0


def angular_separation_degrees(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def conjunction_groups(bodies, threshold: float = NEAR_CONJUNCTION_DEGREES):
    """Return deterministic near-conjunction groups in circular lambda order.

    Each input item is expected to be (key, name, longitude).  Connected
    neighbors within threshold belong to one group, including across 0/360.
    Only groups of two or more bodies are returned.  Members are ordered by
    increasing circular lambda from the group's first member.
    """
    items = sorted(bodies, key=lambda item: item[2] % 360.0)
    if len(items) < 2:
        return []

    gaps = [
        (items[(i + 1) % len(items)][2] - items[i][2]) % 360.0
        for i in range(len(items))
    ]
    breaks = [i for i, gap in enumerate(gaps) if gap > threshold]
    if not breaks:
        return [items]

    start = (breaks[0] + 1) % len(items)
    ordered = items[start:] + items[:start]
    groups = []
    current = [ordered[0]]
    for item in ordered[1:]:
        if angular_separation_degrees(current[-1][2], item[2]) <= threshold:
            current.append(item)
        else:
            if len(current) > 1:
                groups.append(current)
            current = [item]
    if len(current) > 1:
        groups.append(current)
    return groups


class FinderMode'''

if text.count(needle) != 1:
    raise SystemExit(f"Safety stop: geometry insertion point count={text.count(needle)}")
text = text.replace(needle, replacement, 1)
path.write_text(text)

# Add a small independent unit test for the deterministic contract.
test = Path("tests/test_planet_finder_conjunctions.py")
test.write_text('''from planet_finder_geometry import conjunction_groups\n\n\ndef names(groups):\n    return [[item[1] for item in group] for group in groups]\n\n\ndef test_near_conjunction_members_resolve_in_lambda_order():\n    bodies = [("sun", "Sun", 284.644), ("venus", "Venus", 284.239), ("mars", "Mars", 10.0)]\n    assert names(conjunction_groups(bodies)) == [["Venus", "Sun"]]\n\n\ndef test_near_conjunction_wraps_across_zero_degrees():\n    bodies = [("a", "A", 359.8), ("b", "B", 0.2), ("c", "C", 40.0)]\n    assert names(conjunction_groups(bodies)) == [["A", "B"]]\n\n\ndef test_separate_bodies_are_not_groups():\n    bodies = [("a", "A", 10.0), ("b", "B", 20.0), ("c", "C", 30.0)]\n    assert conjunction_groups(bodies) == []\n''')

print("Added mode-independent deterministic conjunction grouping and unit tests.")
