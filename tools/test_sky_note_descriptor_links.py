#!/usr/bin/env python3
"""Regression checks for portable Sky Note descriptor references."""
from __future__ import annotations

import unittest

from sky_note_descriptors import _base, descriptor_href


class SkyNoteDescriptorLinkTests(unittest.TestCase):
    def test_weekly_page_link_is_relative(self) -> None:
        self.assertEqual(descriptor_href("m71"), "../../descriptors/m71.json")

    def test_descriptor_machine_reference_is_relative_to_itself(self) -> None:
        record = _base("m71", "deep-sky-object", "M71", "test descriptor")
        self.assertEqual(record["representation"]["machine"], "./m71.json")


if __name__ == "__main__":
    unittest.main()
