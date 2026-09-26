from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

geometry_path = Path("tools/planet_finder_geometry.py")
test_path = Path("tests/test_planet_finder_conjunctions.py")
geometry = geometry_path.read_text()
tests = test_path.read_text()

old_constant = '''# Bodies closer than this in ecliptic longitude form one deterministic
# near-conjunction group before any presentation-mode search begins.
NEAR_CONJUNCTION_DEGREES = 1.0
'''
new_constant = '''# Bodies closer than this in ecliptic longitude form one deterministic
# near-conjunction group before any presentation-mode search begins.
NEAR_CONJUNCTION_DEGREES = 1.0

# After conjunction members are frozen, remaining bodies within this angular
# neighborhood form broader alignment groups for the second placement phase.
ALIGNMENT_DEGREES = 30.0
'''

anchor = '''    groups.sort(key=lambda group: group[0][2] % 360.0)
    return groups


class FinderMode(str, Enum):
'''
replacement = '''    groups.sort(key=lambda group: group[0][2] % 360.0)
    return groups


def alignment_groups(bodies, threshold: float = ALIGNMENT_DEGREES):
    """Return deterministic broad alignment groups after conjunction removal.

    Near-conjunction members are deliberately excluded: they belong to the
    earlier, more constrained placement phase and will already be frozen before
    alignment placement begins. Remaining connected circular-lambda neighbors
    within ``threshold`` form an alignment group.
    """
    conjunction_names = {
        item[1]
        for group in conjunction_groups(bodies)
        for item in group
    }
    remaining = [item for item in bodies if item[1] not in conjunction_names]
    return conjunction_groups(remaining, threshold=threshold)


class FinderMode(str, Enum):
'''

if geometry.count(old_constant) != 1:
    raise SystemExit(f"Safety stop: conjunction constant block count={geometry.count(old_constant)}")
if geometry.count(anchor) != 1:
    raise SystemExit(f"Safety stop: alignment insertion anchor count={geometry.count(anchor)}")
geometry = geometry.replace(old_constant, new_constant, 1).replace(anchor, replacement, 1)

old_import = 'from planet_finder_geometry import conjunction_groups, conjunction_glyph_radii\n'
new_import = 'from planet_finder_geometry import alignment_groups, conjunction_groups, conjunction_glyph_radii\n'
if tests.count(old_import) != 1:
    raise SystemExit(f"Safety stop: test import count={tests.count(old_import)}")
tests = tests.replace(old_import, new_import, 1)

tests += '''\n\n# Broad alignment classification (<=30 degrees), separate from <=1 degree conjunctions.\ndef test_alignment_classifier_widely_separated_bodies_are_independent():\n    sky = bodies([("Sun", 0.0), ("Mercury", 60.0), ("Venus", 120.0), ("Mars", 180.0)])\n    assert alignment_groups(sky) == []\n\n\ndef test_alignment_classifier_one_broad_alignment():\n    sky = bodies([("Sun", 10.0), ("Venus", 25.0), ("Mars", 100.0)])\n    assert names(alignment_groups(sky)) == [["Sun", "Venus"]]\n\n\ndef test_alignment_classifier_two_independent_alignments():\n    sky = bodies([("Sun", 10.0), ("Venus", 25.0), ("Mars", 160.0), ("Jupiter", 180.0)])\n    assert names(alignment_groups(sky)) == [["Sun", "Venus"], ["Mars", "Jupiter"]]\n\n\ndef test_alignment_classifier_excludes_frozen_conjunction_members():\n    sky = bodies([("Venus", 10.0), ("Sun", 10.4), ("Mars", 20.0), ("Jupiter", 100.0)])\n    assert names(conjunction_groups(sky)) == [["Venus", "Sun"]]\n    assert alignment_groups(sky) == []\n\n\ndef test_alignment_classifier_wraps_across_zero():\n    sky = bodies([("A", 350.0), ("B", 10.0), ("C", 100.0)])\n    assert names(alignment_groups(sky)) == [["A", "B"]]\n\n\ndef test_w1_sun_venus_is_broad_alignment_not_conjunction():\n    sky = bodies([("Venus", 0.0), ("Sun", 2.081), ("Mars", 100.0)])\n    assert conjunction_groups(sky) == []\n    assert names(alignment_groups(sky)) == [["Venus", "Sun"]]\n'''

geometry_path.write_text(geometry)
test_path.write_text(tests)
print("Added separate 30-degree alignment classifier and progressive classification tests.")
