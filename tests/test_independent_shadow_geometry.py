"""Deterministic geometry tests; no ephemeris or network required."""
import math
import unittest
from independent_shadow_geometry import solar_shadow_elements, EARTH_EQUATORIAL_RADIUS_KM


class ShadowGeometryTests(unittest.TestCase):
    def test_aligned_shadow_crosses_earth_center(self):
        sun = (0.0, 0.0, 0.0)
        moon = (149_200_000.0, 0.0, 0.0)
        earth = (149_600_000.0, 0.0, 0.0)
        result = solar_shadow_elements(sun, earth, moon)
        self.assertAlmostEqual(result.gamma, 0.0, places=12)
        self.assertAlmostEqual(result.axis_distance_km, 0.0, places=8)
        self.assertGreater(result.l1, 0.0)
        self.assertTrue(math.isfinite(result.l2))

    def test_offset_moon_shifts_shadow_axis(self):
        sun = (0.0, 0.0, 0.0)
        earth = (149_600_000.0, 0.0, 0.0)
        aligned = solar_shadow_elements(sun, earth, (149_200_000.0, 0.0, 0.0))
        shifted = solar_shadow_elements(sun, earth, (149_200_000.0, 10_000.0, 0.0))
        self.assertGreater(shifted.gamma, aligned.gamma)
        self.assertGreater(shifted.axis_distance_km, EARTH_EQUATORIAL_RADIUS_KM)

    def test_degenerate_positions_rejected(self):
        with self.assertRaises(ValueError):
            solar_shadow_elements((0, 0, 0), (1, 0, 0), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
