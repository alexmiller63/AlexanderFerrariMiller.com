"""Regression tests: finder titles must not claim absent guide stars."""
import unittest

from tools.render_sky_note_finder import verified_planet_finder_title


class PlanetFinderTitleTests(unittest.TestCase):
    def test_visible_labeled_guide_is_named(self):
        self.assertEqual(
            verified_planet_finder_title("Mars", "Sagittarius", "Nunki",
                                         "Sagittarius", True, True),
            "Mars near Nunki in Sagittarius",
        )

    def test_off_field_guide_is_not_named(self):
        self.assertEqual(
            verified_planet_finder_title("Mars", "Sagittarius", "Nunki",
                                         "Sagittarius", False, False),
            "Mars in Sagittarius",
        )

    def test_unlabeled_guide_is_not_named(self):
        self.assertEqual(
            verified_planet_finder_title("Saturn", "Pisces", "Fomalhaut",
                                         "Piscis Austrinus", True, False),
            "Saturn in Pisces",
        )

    def test_visible_labeled_guide_in_other_constellation(self):
        self.assertEqual(
            verified_planet_finder_title("Saturn", "Pisces", "Fomalhaut",
                                         "Piscis Austrinus", True, True),
            "Saturn in Pisces, near Fomalhaut in Piscis Austrinus",
        )

    def test_missing_guide_uses_constellation(self):
        self.assertEqual(
            verified_planet_finder_title("Venus", "Taurus", "", "Taurus",
                                         True, False),
            "Venus in Taurus",
        )


if __name__ == "__main__":
    unittest.main()
