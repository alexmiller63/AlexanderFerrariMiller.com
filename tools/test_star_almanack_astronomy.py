#!/usr/bin/env python3
"""Regression tests for Star Almanack's shared astronomy rules."""
from __future__ import annotations

import unittest

from star_almanack_astronomy import declination_band


class DeclinationBandTests(unittest.TestCase):
    def test_tropical_band_includes_the_tropics(self):
        self.assertEqual(declination_band(-23.44), "Tropical")
        self.assertEqual(declination_band(0), "Tropical")
        self.assertEqual(declination_band(23.44), "Tropical")

    def test_northern_and_southern_temperate_bands(self):
        self.assertEqual(declination_band(23.440001), "Northern")
        self.assertEqual(declination_band(66.559999), "Northern")
        self.assertEqual(declination_band(-23.440001), "Southern")
        self.assertEqual(declination_band(-66.559999), "Southern")

    def test_polar_circles_belong_to_polar_bands(self):
        self.assertEqual(declination_band(66.56), "Arctic")
        self.assertEqual(declination_band(90), "Arctic")
        self.assertEqual(declination_band(-66.56), "Antarctic")
        self.assertEqual(declination_band(-90), "Antarctic")

    def test_known_arctic_star_kochab(self):
        # β UMi, source declination +74.155505°.
        self.assertEqual(declination_band(74.155505), "Arctic")

    def test_rejects_nonphysical_declination(self):
        with self.assertRaises(ValueError):
            declination_band(90.000001)
        with self.assertRaises(ValueError):
            declination_band(-90.000001)


if __name__ == "__main__":
    unittest.main()
