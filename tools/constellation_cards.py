"""Render constellation cards and story pages from canonical Markdown sources."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def metadata(root=ROOT):
    rows = []
    for path in sorted((root / 'stories/constellations').glob('*.md')):
        text = path.read_text(encoding='utf-8')
        if not text.startswith('---\n'):
            continue
        row = {}
        for line in text.split('---', 2)[1].splitlines():
            key, separator, value = line.partition(':')
            if separator:
                value = value.strip()
                row[key.strip()] = json.loads(value) if value.startswith('"') else value
        if not all(row.get(key) for key in ('constellation', 'name', 'hed', 'dek')):
            raise ValueError(f'Missing constellation card metadata: {path}')
        row['slug'] = path.stem
        row['body'] = text.split('---', 2)[2].strip()
        rows.append(row)
    if len(rows) != 88 or len({r['constellation'] for r in rows}) != 88:
        raise ValueError('Expected exactly 88 canonical constellation cards')
    return rows


def page(title, introduction, cards, stylesheet):
    return ('---\nlayout: null\n---\n<!doctype html><html lang="en"><head>'
            '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)} · Star Almanack</title>'
            f'<link rel="stylesheet" href="{stylesheet}">'
            '<style>.constellation-preview{display:block;width:100%;height:auto;aspect-ratio:11/8;object-fit:contain;background:#071527}'
            '.constellation-hed{font-size:1.2rem}.card h2{margin-top:0}.card p{line-height:1.6}</style>'
            '</head><body>{% include star-almanack-nav.html %}<main class="page-shell">'
            f'<section class="hero"><p class="eyebrow">Star Almanack</p><h1>{html.escape(title)}</h1>'
            f'<p class="tagline">{html.escape(introduction)}</p></section>'
            f'<section class="cards" aria-label="{html.escape(title)} cards">'+''.join(cards)+
            '</section></main>{% include star-almanack-footer.html %}</body></html>\n')


def atlas_index(geometry, available, root=ROOT):
    by_abbr = {row['constellation']: row for row in metadata(root)}
    cards = []
    for abbr in available:
        name = geometry[abbr]['name']
        row = by_abbr[abbr]
        slug = abbr.lower()
        cards.append(f'<article class="card" data-constellation="{html.escape(abbr)}">'
                     f'<h2>{html.escape(name)}</h2><a href="{slug}.html">'
                     f'<img class="constellation-preview" src="{slug}.svg" alt="{html.escape(name)} constellation portrait" loading="lazy"></a>'
                     f'<h3 class="constellation-hed">{html.escape(row["hed"])}</h3><p>{html.escape(row["dek"])}</p>'
                     f'<a class="button" href="../../constellations/{row["slug"]}.html">Read the story</a> '
                     f'<a href="{slug}.html">Open the chart</a></article>')
    return page('Constellation Atlas', 'Explore the constellation portraits and their chart layers.', cards,
                '../../css/star-almanack-nav-20261022.css')


def collection(root=ROOT):
    cards = []
    for row in metadata(root):
        abbr, name = row['constellation'], row['name']
        cards.append(f'<article class="card" data-constellation="{html.escape(abbr)}">'
                     f'<h2>{html.escape(name)}</h2><h3 class="constellation-hed">{html.escape(row["hed"])}</h3>'
                     f'<p>{html.escape(row["dek"])}</p>'
                     f'<a class="button" href="{row["slug"]}.html">Read the story</a>' +
                     ('<p><a href="../front-matter.html#whats-up-with-mensa-microscopium-and-serpens">About the figure convention</a></p>'
                      if abbr in ('Men', 'Mic') else '') + '</article>')
    return page('Constellations', 'Names, meanings, and histories of all 88 constellations, with Serpens treated as one.', cards,
                '../css/star-almanack-nav-20261022.css')


def write_collection(root=ROOT):
    target = root / 'star-almanack/constellations/index.html'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(collection(root), encoding='utf-8')
    for row in metadata(root):
        prefix = f'# {row["hed"]}\n\n*{row["dek"]}*'
        if not row['body'].startswith(prefix):
            raise ValueError(f'Unexpected story opening: {row["name"]}')
        body = row['body'][len(prefix):].strip()
        story = ('---\nlayout: null\n---\n<!doctype html><html lang="en"><head>'
                 '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                 f'<title>{html.escape(row["name"])} · Star Almanack</title>'
                 '<link rel="stylesheet" href="../css/star-almanack-nav-20261022.css">'
                 '<style>.constellation-story{max-width:75ch;margin:auto;line-height:1.75}.constellation-story h2{margin-top:2rem}</style>'
                 '</head><body>{% include star-almanack-nav.html %}<main class="page-shell">'
                 '<p><a href="./">All constellations</a></p><header class="hero">'
                 f'<p class="eyebrow">{html.escape(row["name"])}</p><h1>{html.escape(row["hed"])}</h1>'
                 f'<p class="tagline">{html.escape(row["dek"])}</p></header>'
                 + ('<p class="draft-status"><strong>Draft</strong> — accuracy and source-overlap review pending.</p>'
                    if row.get('status') == 'pending' else '') +
                 '<article class="constellation-story">{% capture constellation_story %}\n' + body +
                 '\n{% endcapture %}{{ constellation_story | markdownify }}</article>'
                 f'<p><a class="button" href="../chart-library/constellations/{row["constellation"].lower()}.html">Open the constellation chart</a></p>'
                 '</main>{% include star-almanack-footer.html %}</body></html>\n')
        (target.parent / (row['slug'] + '.html')).write_text(story, encoding='utf-8')


if __name__ == '__main__':
    write_collection()
