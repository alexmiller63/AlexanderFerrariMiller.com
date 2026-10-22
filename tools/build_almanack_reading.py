#!/usr/bin/env python3
"""Publish the Almanack manuscripts as a reading collection without rewriting them.

Run from any directory with: python3 tools/build_almanack_reading.py
The root Markdown manuscripts remain authoritative. Jekyll renders the captured
Markdown; this builder needs only the Python standard library.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'star-almanack'
SECTIONS = (
    ('Opening and reader’s guide', (
        ('signs-and-seasons', 'For Signs and for Seasons', 'The motions of the heavens and the conventions we use to describe them.'),
        ('how-to-use', 'How to Use This Almanack', 'The existing introduction to dates, symbols, charts, and observing.'),
    )),
    ('Stories', (
        ('birthday-libra', 'My Libra Birthday Disappointment', 'The question that led to the Almanack: what can I actually go outside and see tonight?'),
        ('rabbis', 'The Parable of the Two Rabbis', 'Two travelers, two calendars, and the need for a common convention.'),
        ('tyson', 'The Argument with Neil deGrasse Tyson', 'An imagined argument about midnight, 9 PM, and the intended observer.'),
        ('grandmother', 'What Century Was My Grandmother Born In?', 'A family birth date, calendar changes, clock conventions, and an unanswered question.'),
        ('most-ordinary', 'The Most Ordinary Day Throughout the World', 'One deliberately ordinary instant, expressed by many clocks and dates.'),
    )),
    ('Reference text', (
        ('mathematics', 'The Mathematics of the Star Almanack: A Bowl of Jell-O', 'How best visibility was discovered and tested, and why Earth’s rotation complicates eclipse predictions.'),
        ('moon-names', 'Moon Names', 'The retained seasonal naming rules and calculation notes.'),
    )),
)


def shell(title: str, contents: str, mathematics: bool = False) -> str:
    # Zodiac characters default to colored emoji on some devices. Request
    # Unicode text presentation in generated pages, including code examples,
    # while leaving the authoritative Markdown manuscripts untouched.
    contents = re.sub(r'([\u2648-\u2653])[\ufe0e\ufe0f]?', lambda match: match[1] + '\ufe0e', contents)
    math_head = '''
  <script defer src="js/reading-math-20261022.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js"></script>
  <style>.manuscript mjx-container[display="true"] { overflow-x:auto; overflow-y:hidden; max-width:100%; padding:0.3rem 0; }</style>
''' if mathematics else ''
    return '''---
layout: null
---
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>''' + html.escape(title) + ''' · Star Almanack</title>
  <link rel="stylesheet" href="css/star-almanack-nav-20261022.css">
  <link rel="stylesheet" href="css/reading-20261022.css">
''' + math_head + '''</head>
<body>
  {% include_relative includes/nav.html %}
  <main class="page-shell reading-shell">
''' + contents + '''
  </main>
  {% include_relative includes/footer.html %}
</body>
</html>
'''


def build() -> None:
    front_matter = (ROOT / 'front-matter.md').read_text(encoding='utf-8')
    if '{%' in front_matter or '{{' in front_matter:
        raise ValueError('Unexpected Liquid syntax in front-matter.md')
    front_contents = ('{% capture manuscript %}\n' + front_matter
                      + '\n{% endcapture %}\n<article class="prose manuscript">\n'
                      + '{{ manuscript | markdownify }}\n</article>')
    (OUT / 'front-matter.html').write_text(shell('Front Matter', front_contents), encoding='utf-8')
    cards = []
    manuscripts = [entry for _, entries in SECTIONS for entry in entries]
    for index, (slug, title, description) in enumerate(manuscripts):
        source = ROOT / (slug + '.md')
        manuscript = source.read_text(encoding='utf-8')
        # The long-form rabbis manuscript has an unmarked opening title. Mark
        # that one line as a heading, keeping the original words and body intact.
        if slug == 'rabbis':
            first, newline, rest = manuscript.partition('\n')
            if not first.startswith('# '):
                manuscript = '# ' + first + newline + rest
        if '{%' in manuscript or '{{' in manuscript:
            raise ValueError(f'Unexpected Liquid syntax in {source.name}')
        previous = manuscripts[index - 1] if index else None
        following = manuscripts[index + 1] if index + 1 < len(manuscripts) else None
        links = ['<a href="reading.html">All text and stories</a>']
        if previous:
            links.append(f'<a href="read-{previous[0]}.html">← {html.escape(previous[1])}</a>')
        if following:
            links.append(f'<a href="read-{following[0]}.html">{html.escape(following[1])} →</a>')
        navigation = '<nav class="reading-links" aria-label="Reading navigation">' + ''.join(links) + '</nav>'
        technical_link = ('<p><a href="https://github.com/alexmiller63/AlexanderFerrariMiller.com/blob/main/math.md">Read the separate technical mathematical reference</a></p>\n' if slug == 'mathematics' else '')
        contents = navigation + '\n{% capture manuscript %}\n' + manuscript + '\n{% endcapture %}\n<article class="prose manuscript">\n{{ manuscript | markdownify }}\n' + technical_link + '</article>\n' + navigation
        (OUT / f'read-{slug}.html').write_text(shell(title, contents, mathematics=slug == 'mathematics'), encoding='utf-8')
    for label, entries in SECTIONS:
        group = '<section class="reading-group"><h2>' + html.escape(label) + '</h2><div class="cards">'
        for slug, title, description in entries:
            group += f'<article class="card"><h3><a href="read-{slug}.html">{html.escape(title)}</a></h3><p>{html.escape(description)}</p><a class="button" href="read-{slug}.html">Read</a></article>'
        cards.append(group + '</div></section>')
    intro = '''<section class="hero"><p class="eyebrow">Alexander Ferrari Miller</p><h1>Text and Stories</h1><p class="tagline">The ideas, experiences, and questions behind the Star Almanack.</p></section>
<p class="reading-intro">Read the existing manuscripts in sequence, or choose a piece below. These texts retain their original wording, including earlier descriptions of features and working calculation notes.</p>
<p class="reading-intro"><a href="front-matter.html">Open the reconstructed Front Matter</a> for the collected opening material, symbol key, conventions, and recovery notes.</p>
'''
    (OUT / 'reading.html').write_text(shell('Text and Stories', intro + '\n'.join(cards)), encoding='utf-8')
    print(f'Published {len(manuscripts)} manuscripts and the reading index.')


if __name__ == '__main__':
    build()
