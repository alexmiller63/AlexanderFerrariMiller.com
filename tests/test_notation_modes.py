"""Permanent mode IDs and safe migration of existing artwork."""
import unittest
import xml.etree.ElementTree as ET
from tools.notation_modes import NotationMode, refresh_document


class NotationModeTests(unittest.TestCase):
    def test_ids_and_legacy_input_aliases(self):
        self.assertEqual([mode.value for mode in NotationMode], [1, 2, 3])
        for old, number in (("greek", 1), ("latin", 2), ("english", 2), ("mixed", 3)):
            self.assertEqual(NotationMode(old), number)
            self.assertEqual(NotationMode(str(number)), number)
        with self.assertRaises(ValueError):
            NotationMode(4)

    def test_refresh_keeps_geometry_and_is_idempotent(self):
        old = '''<svg data-notation-mode="greek"><style>svg[data-notation-mode="latin"] [id$="-latin"] { display:inline }</style><path d="M 1 2 L 3 4"/><g id="star-label-42-latin"/><text data-notation-choice="latin" role="button">Latin</text><script>root.querySelectorAll('[data-notation-choice]')</script></svg>'''
        new = refresh_document(old)
        root = ET.fromstring(new)
        self.assertEqual(root.get('data-notation-mode'), '1')
        self.assertEqual(root.find('text').get('data-notation-choice'), '2')
        self.assertEqual(root.find('text').text, 'English')
        self.assertEqual(root.find('path').attrib, ET.fromstring(old).find('path').attrib)
        self.assertEqual(root.find('g').attrib, ET.fromstring(old).find('g').attrib)
        self.assertIn('data-notation-mode="2"', root.find('style').text)
        self.assertIn("latin:'2'", root.find('script').text)
        self.assertEqual(refresh_document(new), new)


if __name__ == '__main__':
    unittest.main()
