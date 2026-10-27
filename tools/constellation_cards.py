"""Shared editorial cards for the constellation collection and portrait atlas."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'constellation-cards.json').read_text())
CARDS = DATA['constellations']
STYLE = '''body{margin:0;background:#071527;color:#e8f3ff;font:16px/1.6 system-ui}main{max-width:1200px;margin:auto;padding:1rem}a{color:#8fd5ff}h1{line-height:1.2}.card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:1rem}.constellation-card{padding:1.2rem;border:1px solid #7d9bb5;border-radius:.65rem;background:#10263b;scroll-margin-top:1rem}.constellation-card h2{margin:.25rem 0;color:#d9efff;line-height:1.3}.constellation-card p{color:#a9c8dd}.constellation-card .name{color:#69dc94;font-weight:700;margin:0}.constellation-card img{width:100%;aspect-ratio:11/8;object-fit:contain;background:#071527}.card-links{display:flex;flex-wrap:wrap;gap:1rem}svg{width:100%;height:auto}nav{display:flex;flex-wrap:wrap;gap:1rem;padding:1rem 0}'''


def card(abbr, portraits, prefix='', collection='../constellations/', show_collection=True, show_portraits=True):
    entry = CARDS[abbr]
    e = html.escape
    links = ''.join(f'<a href="{e(prefix + key.lower())}.html">{e(name)} portrait</a>' for key, name in portraits)
    if not portraits and abbr in {"Men", "Mic"}:
        links = '<a href="../front-matter.html#whats-up-with-mensa-microscopium-and-serpens">Why no stick figure?</a>'
    if not show_portraits:
        links = ""
    if show_collection:
        links += f'<a href="{collection}#{abbr.lower()}">Constellation collection</a>'
    preview = (f'<img loading="lazy" src="{html.escape(prefix + portraits[0][0].lower())}.svg" alt="{e(portraits[0][1])} stick-figure portrait">' if portraits else '')
    return (f'<article class="constellation-card" id="{abbr.lower()}">'
            f'{preview}<p class="name"> {e(entry["name"])}</p><h2>{e(entry["hed"])}</h2>'
            f'<p>{e(entry["dek"])}</p><div class="card-links">{links}</div></article>')


def document(title, content):
    return ('---\nlayout: null\n---\n<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{STYLE}</style></head><body><main>'
            f'<h1>{html.escape(title)}</h1>{content}</main></body></html>\n')


def generate_collection(portraits):
    assert len(CARDS) == 88 and 'Ser' in CARDS
    by_subject = {abbr: [] for abbr in CARDS}
    for key, name in portraits:
        by_subject['Ser' if key.startswith('Ser') else key].append((key, name))
    content = '<p><a href="../chart-library/constellations/">Constellation Atlas</a> · <a href="../chart-library/">Chart Library</a></p><p>All 88 constellations, with one card for Serpens and links to its two portraits.</p><div class="card-grid">'
    content += ''.join(card(abbr, by_subject[abbr], prefix='../chart-library/constellations/', show_collection=False)
                       for abbr in sorted(CARDS, key=lambda k: CARDS[k]['name']))
    content += '</div><p>Sources: ' + ' · '.join(f'<a href="{html.escape(url)}">{label}</a>' for url, label in zip(DATA['sources'], ['IAU constellations', 'Wolbach Library: names and origins'])) + '</p>'
    out = ROOT / 'star-almanack/constellations'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'index.html').write_text(document('Constellations', content), encoding='utf-8')
