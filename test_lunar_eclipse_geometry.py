"""Unit tests for lunar shadow geometry, independent of ephemeris data."""
import unittest
from lunar_eclipse_geometry import lunar_shadow_geometry


class LunarShadowGeometryTests(unittest.TestCase):
    SUN = (149_597_870.7, 0.0, 0.0)

    def test_central_total_eclipse(self):
        g = lunar_shadow_geometry(self.SUN, (-384_400.0, 0.0, 0.0))
        self.assertEqual(g.classification, "total")
        self.assertGreater(g.totality_margin_km, 0)
        self.assertGreater(g.penumbra_radius_km, g.umbra_radius_km)

    def test_moon_sunward_of_earth(self):
        g = lunar_shadow_geometry(self.SUN, (384_400.0, 0.0, 0.0))
        self.assertEqual(g.classification, "none")

    def test_partial_eclipse(self):
        g = lunar_shadow_geometry(self.SUN, (-384_400.0, 4000.0, 0.0))
        self.assertEqual(g.classification, "partial")
        self.assertGreaterEqual(g.umbral_margin_km, 0)
        self.assertLess(g.totality_margin_km, 0)

    def test_penumbral_eclipse(self):
        g = lunar_shadow_geometry(self.SUN, (-384_400.0, 8000.0, 0.0))
        self.assertEqual(g.classification, "penumbral")
        self.assertGreaterEqual(g.penumbral_margin_km, 0)
        self.assertLess(g.umbral_margin_km, 0)

    def test_miss(self):
        g = lunar_shadow_geometry(self.SUN, (-384_400.0, 15000.0, 0.0))
        self.assertEqual(g.classification, "none")

    def test_frame_rotation_invariance(self):
        a = lunar_shadow_geometry(self.SUN, (-384_400.0, 4000.0, 0.0))
        b = lunar_shadow_geometry((0.0, 149_597_870.7, 0.0), (-4000.0, -384_400.0, 0.0))
        self.assertAlmostEqual(a.axis_offset_km, b.axis_offset_km, places=6)
        self.assertEqual(a.classification, b.classification)


if __name__ == "__main__":
    unittest.main()
