"""Reader-facing notation and guide-star placement regressions."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.transforms import Bbox
from tools.constellation_names import constellation_names

from tools.render_sky_note_finder import (
    add_constellation_notation, marker_obstacle_bbox, place_star_notation, place_body_notation, place_ecliptic_notation,
    segment_hits_display_bbox, star_notation_labels, visible_ecliptic_signs,
)


class StarNotationTests(unittest.TestCase):
    def setUp(self):
        self.fig, self.ax = plt.subplots(figsize=(8.2, 8.2))
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)
        self.fig.canvas.draw()
        self.identity = dict(fixed_object_id=42, bayer="Bet Psc",
                             proper_name="Fumalsamakah", constellation_abbreviation="Psc")
        self.star = SimpleNamespace(proper="Fumalsamakah", bayer="Bet", con="Psc")

    def tearDown(self):
        plt.close(self.fig)

    def test_zodiac_sectors_wrap_at_aries_and_stay_inside_chart(self):
        signs = visible_ecliptic_signs((0, 0), -5, 5, -5, 5)
        self.assertEqual({name for _, name, _ in signs}, {"Aries", "Pisces"})
        self.assertEqual({symbol for symbol, _, _ in signs}, {"♈", "♓"})
        for _, _, (x, y) in signs:
            self.assertTrue(-5 <= x <= 5 and -5 <= y <= 5)
        opposite = visible_ecliptic_signs((180, 0), -5, 5, -5, 5)
        self.assertEqual({name for _, name, _ in opposite}, {"Virgo", "Libra"})

    def test_ecliptic_names_the_sign_rather_than_the_constellation(self):
        placed = place_ecliptic_notation(self.ax, "♈", "Aries", (0.5, 0.5), [])
        self.assertEqual({mode: label.get_text() for mode, label in placed.items()},
                         {"greek": "♈", "latin": "Sign of Aries", "mixed": "♈ Sign of Aries"})

    def test_mercury_body_label_switches_with_notation(self):
        placed = place_body_notation(self.ax, "Mercury", (0.5, 0.5), [], target=True)
        self.assertEqual({mode: label.get_text() for mode, label in placed.items()},
                         {"greek": "☿", "latin": "Mercury", "mixed": "☿ Mercury"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "finder.svg"
            self.fig.savefig(path)
            add_constellation_notation(path)
            root = ET.parse(path).getroot()
            ids = {node.get("id") for node in root.iter()}
            for mode in ("greek", "latin", "mixed"):
                self.assertIn(f"body-label-mercury-{mode}", ids)
            style = root.find("{http://www.w3.org/2000/svg}style").text
            self.assertIn('svg[data-notation-mode="2"] [id^="body-label-"][id$="-latin"]', style)
            self.assertIn('svg[data-notation-mode="3"] [id^="body-label-"][id$="-mixed"]', style)

    def test_greek_star_symbol_and_named_variants(self):
        labels = star_notation_labels(self.identity, self.star, "Psc", target=True)
        self.assertEqual(labels["greek"], "β")
        self.assertEqual(labels["latin"], "Fumalsamakah")
        self.assertEqual(labels["mixed"], "Beta Piscium\nFumalsamakah")

    def test_pisces_keeps_its_name_in_mixed_mode(self):
        identity, names = constellation_names("Pisces", "Psc")
        self.assertEqual(identity, "Psc")
        self.assertEqual(names["mixed"], "Pisces")

    def test_beta_piscium_mixed_label_retains_designation_without_proper_name(self):
        identity = dict(self.identity, proper_name="")
        star = SimpleNamespace(proper="", bayer="Bet", con="Psc")
        self.assertEqual(star_notation_labels(identity, star, "Psc")["mixed"], "Beta Piscium")

    def test_each_variant_clears_ring_and_reserved_text(self):
        point = (0.5, 0.5)
        ring = marker_obstacle_bbox(self.ax, point, 210, 2.6)
        occupied = [ring]
        placed = place_star_notation(
            self.ax, self.identity,
            star_notation_labels(self.identity, self.star, "Psc", target=True),
            point, occupied, target=True,
        )
        self.fig.canvas.draw()
        renderer = self.fig.canvas.get_renderer()
        self.assertEqual(set(placed), {"greek", "latin", "mixed"})
        for annotation in placed.values():
            box = annotation.get_window_extent(renderer)
            self.assertFalse(box.overlaps(ring))
            self.assertTrue(self.ax.bbox.contains(box.x0, box.y0))
            self.assertTrue(self.ax.bbox.contains(box.x1, box.y1))
        # A short symbol should sit close to its star rather than inheriting
        # the displacement needed by a longer named variant.
        beta = placed["greek"].get_window_extent(renderer)
        anchor = self.ax.transData.transform(point)
        distance = min(abs(beta.x0 - anchor[0]), abs(beta.x1 - anchor[0]))
        self.assertLess(distance * 72 / self.fig.dpi, 25)

    def test_later_star_clears_all_notation_variants(self):
        occupied = []
        first = place_star_notation(
            self.ax, self.identity,
            star_notation_labels(self.identity, self.star, "Psc"), (0.5, 0.5), occupied,
        )
        second = place_star_notation(
            self.ax, dict(self.identity, fixed_object_id=43),
            {"greek": "λ", "latin": "Lambda Piscium", "mixed": "λ — Lambda Piscium"},
            (0.52, 0.5), occupied,
        )
        self.fig.canvas.draw()
        renderer = self.fig.canvas.get_renderer()
        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 3)
        for a in first.values():
            for b in second.values():
                self.assertFalse(a.get_window_extent(renderer).overlaps(b.get_window_extent(renderer)))

    def test_standalone_svg_switches_star_groups_with_constellations(self):
        place_star_notation(
            self.ax, self.identity,
            star_notation_labels(self.identity, self.star, "Psc"), (0.5, 0.5), [],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "finder.svg"
            self.fig.savefig(path)
            add_constellation_notation(path)
            root = ET.parse(path).getroot()
            ids = {node.get("id") for node in root.iter()}
            for mode in ("greek", "latin", "mixed"):
                self.assertIn(f"star-label-42-{mode}", ids)
            style = root.find("{http://www.w3.org/2000/svg}style").text
            self.assertIn('[id^="star-label-"][id$="-latin"]', style)
            self.assertIn('svg[data-notation-mode="3"] [id^="star-label-"]', style)

    def test_displaced_leader_path_switches_with_its_label(self):
        x, y = self.ax.transData.transform((0.5, 0.5))
        placed = place_star_notation(
            self.ax, self.identity, {"latin": "Fumalsamakah"}, (0.5, 0.5),
            [Bbox.from_extents(x - 35, y - 35, x + 35, y + 35)], target=True,
        )
        self.assertIn("latin", placed)
        leaders = [text for text in self.ax.texts if text.arrow_patch is not None]
        self.assertEqual(len(leaders), 1)
        self.assertEqual(leaders[0].arrow_patch.get_gid(), "star-label-42-leader-path-latin")

    def test_segment_measurements_follow_changed_axes_geometry(self):
        x, y = self.ax.transData.transform((0.5, 0.5))
        box = Bbox.from_extents(x - 10, y - 10, x + 10, y + 10)
        start, end = (0.4, 0.5), (0.6, 0.5)
        self.assertTrue(segment_hits_display_bbox(self.ax, start, end, box))
        self.ax.set_xlim(0, 10)
        self.assertFalse(segment_hits_display_bbox(self.ax, start, end, box))
        self.ax.set_xlim(0, 1)
        self.assertTrue(segment_hits_display_bbox(self.ax, start, end, box))
        self.ax.set_xscale("log")
        self.ax.set_xlim(0.1, 10)
        self.assertFalse(segment_hits_display_bbox(self.ax, start, end, box))


if __name__ == "__main__":
    unittest.main()

