#!/usr/bin/env python3
"""Idempotent calculated eclipse publication overlay; does not run Build All."""
import argparse, csv, html, io, json, re
from datetime import date
from pathlib import Path
from eclipse_editorial import load_events, render_page, record_downloads
from eclipse_calendar import populate_eclipse_calendar
from eclipse_path import path_geojson
ROOT=Path(__file__).resolve().parents[1]
START='<!-- ECLIPSE-OVERLAY START -->'
END='<!-- ECLIPSE-OVERLAY END -->'
def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists() or path.read_text(encoding='utf-8')!=value:
        path.write_text(value,encoding='utf-8')
def render_index(rows):
    """General eclipse guide followed by the complete event catalog."""
    years = sorted({date.fromisoformat(e["date_utc"]).year for e in rows})
    span = f"{years[0]}–{years[-1]}"
    catalog = '<section id="catalog"><h2>Eclipse catalog · ' + span + '</h2>'
    catalog += '<p>Choose a year, then an event to open its eclipse card.</p>'
    catalog += '<nav aria-label="Catalog years">' + ' · '.join(
        f'<a href="#year-{year}">{year}</a>' for year in years) + '</nav>'
    for year in years:
        catalog += f'<h3 id="year-{year}">{year}</h3><ul>'
        for e in sorted(rows, key=lambda item: (item["date_utc"], item["id"])):
            if date.fromisoformat(e["date_utc"]).year != year:
                continue
            label = f'{e["type"].capitalize()} {e["kind"]} eclipse'
            catalog += (f'<li><a href="/almanack/eclipses/{html.escape(e["id"], quote=True)}.html">'
                        f'{html.escape(e["date_utc"])} — {html.escape(label)}</a></li>')
        catalog += '</ul>'
    catalog += '</section>'
    introduction = "<header><p class=\"eyebrow\">Star Almanack · A guide to the changing sky</p><h1>Eclipses</h1><p class=\"intro\">The Sun, Earth, and Moon write their alignments in shadow. An eclipse lets us watch that geometry unfold.</p></header>\n<nav aria-label=\"On this page\"><a href=\"#why\">Why eclipses happen</a> · <a href=\"#solar\">Solar eclipses</a> · <a href=\"#lunar\">Lunar eclipses</a> · <a href=\"#observing\">Watching safely</a> · <a href=\"#catalog\">Eclipse catalog</a></nav>\n<section id=\"why\"><h2>Why eclipses happen</h2><p>A solar eclipse happens at new Moon, when the Moon passes between Earth and the Sun. A lunar eclipse happens at full Moon, when the Moon passes through Earth’s shadow.</p><p>Why not every month? The Moon’s orbit is tilted by about five degrees to Earth’s orbital plane. Most new and full Moons pass above or below the alignment needed for an eclipse. Eclipses become possible near the two places where those planes cross, called the orbital nodes.</p><p>A shadow has two main regions. In the <strong>umbra</strong>, the light source is completely hidden; in the <strong>penumbra</strong>, only part of it is hidden. The Moon’s central shadow also has an extension called the <strong>antumbra</strong>, where the Moon appears smaller than the Sun and a bright ring remains.</p></section>\n<section id=\"solar\"><h2>Solar eclipses: the Moon’s shadow on Earth</h2><p>A solar eclipse is a local experience. Two people watching the same event from different places can see very different amounts of the Sun covered. A narrow central track may receive totality or annularity while a much larger surrounding region sees a partial eclipse.</p><dl><dt>Total</dt><dd>The Moon completely covers the Sun’s bright disk along the path of totality. The corona becomes visible, daylight fades, and the surrounding horizon may glow.</dd><dt>Annular</dt><dd>The Moon appears too small to cover the entire Sun. Along the central path, sunlight forms a ring around the Moon. The ring remains dangerously bright.</dd><dt>Partial</dt><dd>The Moon covers only part of the Sun. An event classified as partial has no total or annular central path on Earth.</dd><dt>Hybrid</dt><dd>The central eclipse changes between annular and total along its track. Earth’s curved surface changes the observer’s distance from the Moon enough to make the difference. The classification describes different places along one event’s path.</dd></dl><p>The apparent sizes of the Sun and Moon are close, but neither stays exactly constant. Their changing distances help determine whether the Moon can hide the Sun completely.</p></section>\n<section id=\"lunar\"><h2>Lunar eclipses: Earth’s shadow on the Moon</h2><p>During a lunar eclipse, everyone who can see the Moon sees the same phase at the same instant. Whether you can watch the beginning, middle, or end depends on moonrise, moonset, and local conditions.</p><dl><dt>Penumbral</dt><dd>The Moon crosses only the penumbra. Look for subtle shading rather than a sharply defined dark bite; shallow events can be hard to notice.</dd><dt>Partial</dt><dd>Part of the Moon enters the umbra. Earth’s curved shadow advances across the familiar lunar surface.</dd><dt>Total</dt><dd>The whole Moon enters the umbra. Sunlight passing through Earth’s atmosphere can still reach it, giving the Moon copper, orange, or red tones. Its appearance varies with conditions in Earth’s atmosphere.</dd></dl></section>\n<section id=\"observing\"><h2>Watching safely</h2><p><strong>Lunar eclipses are safe to watch directly.</strong> Binoculars reveal changes across the lunar surface.</p><p>For direct solar viewing, use undamaged eclipse glasses or a handheld solar viewer meeting ISO 12312-2. Ordinary sunglasses are unsuitable. Cameras, binoculars, and telescopes need purpose-made solar filters secured over the front of the optics; eclipse glasses alone do not make those instruments safe.</p><p>Only during complete totality, at a location inside the totality path, may you look without a solar viewer. Replace it before the Sun’s bright surface reappears. Keep protection in place throughout partial and annular phases. Indirect pinhole projection offers another way to follow the changing solar crescent without looking at the Sun.</p></section>\n<section><h2>Reading an eclipse card</h2><p>Each catalog link opens an individual event card with explanations, UTC times, calculated geometry, and available path information. UTC is a shared time standard: convert both the date and clock time to your location.</p><p>Greatest eclipse is one instant for the event as a whole. Global beginning and ending times describe the eclipse somewhere on Earth; they are not your local contact times or your duration of totality.</p><p>Our calculated central-path plots show latitude and longitude along the shadow axis, with coordinate downloads. The center line does not show the track’s width or the wider partial-eclipse visibility region. The current spherical-Earth model has limitations described on each card. Calculation records are available through download links.</p></section>"
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Eclipses — Star Almanack</title><style>'
            'body{max-width:760px;margin:2rem auto;padding:0 1rem;background:#fffdf8;'
            'color:#202833;font:1.12rem/1.65 Georgia,serif}'
            'h1,h2,h3{color:#17344d;line-height:1.2}h1{font-size:2.8rem}'
            'section{margin:2.5rem 0}a{color:#245c86}nav{line-height:2}'
            '.eyebrow{font-size:.85em;color:#635b4b}.intro{font-size:1.2em}'
            'dt{font-weight:bold}dd{margin:0 0 1rem}li{margin:.55rem 0}'
            'footer{border-top:1px solid #ccc;padding-top:1rem;font-size:.9em}'
            ':target{scroll-margin-top:1rem}</style></head><body><main>'
            '<nav aria-label="Breadcrumb"><a href="/star-almanack/">Star Almanack</a> / Eclipses</nav>'
            + introduction + catalog +
            '<footer><h2>Sources</h2><p>'
            '<a href="https://science.nasa.gov/eclipses/types/">NASA: eclipse types</a> · '
            '<a href="https://science.nasa.gov/moon/lunar-eclipses/">NASA: lunar eclipses</a> · '
            '<a href="https://science.nasa.gov/eclipses/safety/">NASA: solar viewing safety</a>'
            '</p><p>Event times, geometry, and calculated central tracks: Star Almanack. '
            'See individual cards for calculation methods, limitations, and other sources.</p></footer>'
            '</main></body></html>')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--catalog',type=Path,required=True)
    a=p.parse_args()
    data=json.loads(a.catalog.read_text(encoding='utf-8'))
    rows=data['eclipses']
    if not rows: raise ValueError('Empty eclipse catalog')
    publication_events = load_events(ROOT)
    weeks={}
    for e in rows:
        day=date.fromisoformat(e['date_utc'])
        eid=e['id']
        if not re.fullmatch(r'ECL-\d{4}-\d{2}-\d{2}-[SL]',eid): raise ValueError('Unsafe eclipse ID: '+eid)
        title=f"{e['type'].title()} {e['kind'].title()} Eclipse"
        url=f"/almanack/eclipses/{eid}.html"
        publication_event = {**e, **{key: value for key, value in publication_events.get(eid, {}).items() if key in ("magnitude", "visibility", "observing_note", "earlier_calculation", "earlier_method", "visibility_reference")}}
        detail=render_page(publication_event)
        for filename, content in record_downloads(publication_event).items():
            write(ROOT/'almanack/eclipses'/filename, content)
        write(ROOT/'almanack'/f'eclipses/{eid}.html',detail)
        if e.get('central_path', {}).get('points'):
            track = e['central_path']['points']
            buffer = io.StringIO(newline='')
            writer = csv.DictWriter(buffer, fieldnames=list(track[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(track)
            write(ROOT/'almanack'/f'eclipses/{eid}-path.csv', buffer.getvalue())
            write(ROOT/'almanack'/f'eclipses/{eid}-path.geojson',
                  json.dumps(path_geojson(e), indent=2) + '\n')
        if 2025<=day.year<=2027:
            y,w,_=day.isocalendar()
            weeks.setdefault((y,w),[]).append((day,title,url))
    for (y,w),events in weeks.items():
        page=ROOT/'almanack'/str(y)/f'W{w:02d}'/'index.html'
        if not page.exists():
            print('SKIP missing weekly page',page)
            continue
        content=page.read_text(encoding='utf-8')
        content=populate_eclipse_calendar(content, page, publication_events)
        links=''.join(f'<li><time datetime="{d}">{d}</time>: <a href="{u}">{html.escape(t)}</a></li>' for d,t,u in events)
        block=f'{START}<section id="eclipse-events" aria-label="Eclipses this week"><h2>Eclipses this week</h2><ul>{links}</ul></section>{END}'
        if START in content and END in content:
            content=re.sub(re.escape(START)+r'.*?'+re.escape(END),lambda _:block,content,flags=re.S)
        elif '</main>' in content:
            content=content.replace('</main>',block+'</main>',1)
        else:
            print('SKIP weekly page without main',page)
            continue
        write(page,content)
    index=render_index(rows)
    write(ROOT/'almanack/eclipses/index.html',index)
    print('Published',len(rows),'calculated eclipse pages; updated',len(weeks),'candidate weeks')
if __name__=='__main__':main()


