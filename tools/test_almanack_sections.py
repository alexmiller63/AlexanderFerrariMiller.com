"""Legacy regeneration must preserve neighboring generated content."""
import unittest

from almanack_sections import replace_section_inner, section_bounds


class LegacySectionTests(unittest.TestCase):
    def test_ephemeris_upgrade_preserves_calendar_and_finder_controls(self):
        prefix = '<main>Calendar content</table>'
        suffix = ('<div class="bayer-toggle-wrap section-notation-toggle" '
                  'data-notation-target="finder">controls</div>'
                  '<h3>Planet Finder</h3><img src="finder.svg"></main>')
        text = prefix + '<h3>Weekly Solar-System Ephemeris</h3>old tables' + suffix
        result = replace_section_inner(text, 3, 'new ephemeris')
        self.assertTrue(result.startswith(prefix))
        self.assertTrue(result.endswith(suffix))
        start, end = section_bounds(result, 3)
        self.assertEqual(result[start:end], 'new ephemeris')
        self.assertEqual(replace_section_inner(result, 3, 'new ephemeris'), result)

    def test_sky_note_upgrade_preserves_chart_and_finder(self):
        prefix = '<main><img src="finder.svg">'
        suffix = '<h3>Chart</h3>chart slot</main>navigation'
        for heading in ('Sky Note', 'Sky Notes'):
            with self.subTest(heading=heading):
                result = replace_section_inner(prefix + f'<h3>{heading}</h3>old prose' + suffix,
                                               5, 'linked stories')
                self.assertTrue(result.startswith(prefix))
                self.assertTrue(result.endswith(suffix))
                start, end = section_bounds(result, 5)
                self.assertEqual(result[start:end], 'linked stories')

    def test_ambiguous_or_unrecognized_legacy_markup_is_rejected(self):
        for text in ('<h3>Sky Note</h3>no boundary',
                     '<h3>Sky Note</h3><h3>Sky Note</h3><h3>Chart</h3>',
                     '<h3>Chart</h3><h3>Sky Note</h3>'):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                replace_section_inner(text, 5, 'replacement')


if __name__ == '__main__':
    unittest.main()
