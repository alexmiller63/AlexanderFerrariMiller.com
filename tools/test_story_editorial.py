import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from story_editorial import clean_story, render_inline, source_urls
from fixed_object_stories import Story, write_public_story


class EditorialTests(unittest.TestCase):
    def test_attribution_moves_as_a_whole(self):
        for sentence in (
            'IC 5146 is embedded in a nebula, according to [SIMBAD](https://example.org/ic5146).',
            'According to [SIMBAD](https://example.org/ic5146), IC 5146 is embedded in a nebula.',
        ):
            cleaned = clean_story(sentence)
            self.assertNotIn('according to', cleaned.lower())
            self.assertEqual(source_urls(sentence), source_urls(cleaned))
            self.assertIn('5146', cleaned)
            self.assertEqual(clean_story(cleaned), cleaned)

    def test_predicate_retains_its_source_object(self):
        result = clean_story('The position is listed by [SIMBAD](https://example.org).')
        self.assertIn('listed by the catalogue.', result)

    def test_factual_link_label_survives(self):
        result = clean_story('According to [the authors](https://example.org), the value is uncertain.')
        self.assertIn('According to the authors, the value is uncertain.', result)

    def test_reader_renders_dek_and_escapes_html(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('fixed_object_stories.STORIES_ROOT', Path(folder)):
                story = Story('drafts', 421, Path('421.md'), 'Cocoon', '*A cluster* <script>', 'Body.')
                page = write_public_story(story).read_text()
                self.assertIn('<em>A cluster</em> &lt;script&gt;', page)
                self.assertNotIn('*A cluster*', page)
                self.assertNotIn('<script>', page)
        self.assertIn('<strong>bold</strong>', render_inline('**bold**'))


if __name__ == '__main__':
    unittest.main()
