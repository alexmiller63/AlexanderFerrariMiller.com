#!/usr/bin/env python3
"""Regression checks for curated Sky Note observing guides."""
from __future__ import annotations

import unittest

import populate_sky_notes_by_date as notes
from sky_note_descriptors import build_descriptors, decorate_note_html, human_sentence


class SkyNoteGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stars = notes.load_bright_stars()

    def descriptor_for(self, name: str) -> dict:
        records = build_descriptors(
            [{"type": "star", "name": name, "constellation": next(
                star["con"] for star in self.stars if star["name"] == name
            )}],
            [],
            self.stars,
            notes.CONSTELLATION_NAMES,
            notes.ASTERISMS,
        )
        return next(record for record in records if record["id"] == f"star-{name.lower()}")

    def test_spica_has_curated_asterisms_and_star_hop(self) -> None:
        spica = self.descriptor_for("Spica")
        self.assertEqual(
            [guide["name"] for guide in spica["guiding_asterisms"]],
            ["Spring Triangle", "Great Diamond", "Big Dipper"],
        )
        self.assertEqual(spica["guiding_asterisms"][0]["relationship"], "visual-member")
        self.assertEqual(spica["guiding_asterisms"][2]["relationship"], "star-hop-anchor")
        self.assertEqual(
            spica["guiding_asterisms"][0]["provenance"]["supports"],
            "visual-membership",
        )
        self.assertEqual(
            spica["guiding_asterisms"][2]["relationship_route_ids"],
            ["big-dipper-arcturus-spica"],
        )
        self.assertEqual(
            spica["star_hops"][0]["steps"],
            ["Big Dipper", "Arcturus", "Spica"],
        )
        self.assertEqual(spica["star_hops"][0]["provenance"]["supports"], "star-hop-method")
        self.assertEqual(spica["star_hops"][0]["provenance"]["source_role"], "verification")
        self.assertEqual(
            spica["star_hops"][0]["instruction_authorship"],
            "Star Almanack original wording",
        )
        prose = human_sentence(spica)
        self.assertIn("Spring Triangle", prose)
        self.assertIn("Big Dipper", prose)
        self.assertIn("Arcturus", prose)

    def test_aldebaran_has_curated_guides(self) -> None:
        aldebaran = self.descriptor_for("Aldebaran")
        self.assertEqual(
            [guide["name"] for guide in aldebaran["guiding_asterisms"]],
            ["Hyades / V of Taurus", "Winter Hexagon / Winter Circle", "Orion's Belt"],
        )
        self.assertEqual(aldebaran["star_hops"][0]["steps"][0], "Orion's Belt")

    def test_star_without_curated_route_gets_no_invented_guide(self) -> None:
        alnair = self.descriptor_for("Alnair")
        self.assertEqual(alnair["constellation"], "Grus")
        self.assertNotIn("guiding_asterisms", alnair)
        self.assertNotIn("star_hops", alnair)

    def test_m29_has_independently_verified_northern_cross_star_hop(self) -> None:
        records = build_descriptors(
            [{"type": "deep-sky", "name": "M29, open cluster in Cygnus"}],
            [],
            self.stars,
            notes.CONSTELLATION_NAMES,
            notes.ASTERISMS,
        )
        m29 = next(record for record in records if record["id"] == "m29")
        self.assertEqual(m29["guiding_asterisms"][0]["name"], "Northern Cross")
        self.assertEqual(m29["star_hops"][0]["steps"], ["Northern Cross", "Sadr", "M29"])
        self.assertEqual(m29["star_hops"][0]["provenance"]["source"], "Astronomy Magazine")
        self.assertEqual(m29["star_hops"][0]["provenance"]["supports"], "star-hop-method")

    def test_enif_has_independently_verified_route(self) -> None:
        enif = self.descriptor_for("Enif")
        self.assertEqual(enif["guiding_asterisms"][0]["name"], "Great Square of Pegasus")
        self.assertEqual(enif["star_hops"][0]["steps"], ["Great Square of Pegasus", "Enif"])
        self.assertEqual(enif["star_hops"][0]["provenance"]["source"], "Sky & Telescope")
        self.assertEqual(enif["star_hops"][0]["provenance"]["supports"], "star-hop-method")


    def test_observing_method_headings_link_to_machine_descriptors(self) -> None:
        records = build_descriptors(
            [],
            [],
            self.stars,
            notes.CONSTELLATION_NAMES,
            notes.ASTERISMS,
        )
        rendered = (
            "<p><strong>Naked eye:</strong> Bright targets.</p>"
            "<p><strong>Binoculars:</strong> Wide fields.</p>"
            "<p><strong>Small telescope:</strong> Compact targets.</p>"
        )
        decorated = decorate_note_html(rendered, records)
        self.assertIn(
            '<strong><a class="descriptor-link" href="../../descriptors/naked-eye.json" '
            'type="application/json">Naked eye</a>:</strong>',
            decorated,
        )
        self.assertIn(
            '<strong><a class="descriptor-link" href="../../descriptors/binoculars.json" '
            'type="application/json">Binoculars</a>:</strong>',
            decorated,
        )
        self.assertIn(
            '<strong><a class="descriptor-link" href="../../descriptors/small-telescope.json" '
            'type="application/json">Small telescope</a>:</strong>',
            decorated,
        )


if __name__ == "__main__":
    unittest.main()
