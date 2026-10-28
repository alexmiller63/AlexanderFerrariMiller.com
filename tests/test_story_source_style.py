"""Regression checks for narrative/source separation and safe link rendering."""
import sys
import unittest
from pathlib import Path
from html.parser import HTMLParser
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from story_source_style import clean_story_sources, render_story_body

URL = 'https://simbad.cds.unistra.fr/simbad/sim-id?Ident=HIP%20677'

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a': self.links.append(dict(attrs)['href'])

class SourceStyleTests(unittest.TestCase):
    def test_science_and_post_citation_sentence_survive(self):
        original = 'SIMBAD gives a parallax of 3.78 ± 0.34 milliarcseconds. Source: [SIMBAD](' + URL + '). This is an estimate, not a distance solution.'
        result = clean_story_sources(original)
        prose, sources = result.split('## Sources')
        self.assertNotIn('SIMBAD', prose)
        self.assertIn('3.78 ± 0.34 milliarcseconds', prose)
        self.assertIn('This is an estimate, not a distance solution.', prose)
        self.assertIn(URL, sources)
        self.assertEqual(result, clean_story_sources(result))

    def test_source_inside_link_label_is_not_split(self):
        citation = '[Source: Research paper (2007)](https://example.org/paper)'
        result = clean_story_sources('SIMBAD records the star. ' + citation + '\n\nSource: [SIMBAD](' + URL + ').')
        self.assertIn(citation, result)

    def test_existing_footer_has_one_heading(self):
        original = 'SIMBAD lists a magnitude of 2.83.\n\n**Sources:**\n\n- [SIMBAD](' + URL + ')'
        result = clean_story_sources(original)
        self.assertEqual(result.count('## Sources'), 1)
        self.assertEqual(result, clean_story_sources(result))

    def test_unlinked_provenance_is_not_silently_removed(self):
        text = 'SIMBAD identifies the target, but no citation was supplied.'
        self.assertEqual(clean_story_sources(text), text)

    def test_renderer_clicks_sources_and_escapes_markup(self):
        result = render_story_body('<script>alert(1)</script>\n\n## Sources\n\n- [SIMBAD](' + URL + ')\n\nResearch: https://example.org/?a=1&b=2.')
        self.assertNotIn('<script>', result)
        self.assertIn('<h2>Sources</h2>', result)
        parser = Links(); parser.feed(result)
        self.assertEqual(parser.links, [URL, 'https://example.org/?a=1&b=2'])

if __name__ == '__main__': unittest.main()
