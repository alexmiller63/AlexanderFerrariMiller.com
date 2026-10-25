"""Meteor-shower pages and weekly notes from stored Almanack calculations."""
import html
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def event_id(event):
    name = event['name'].replace('η', 'eta').replace('δ', 'delta').replace('α', 'alpha')
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return f"MET-{event['utc'][:4]}-{slug}"


def href(event):
    return f'/almanack/meteors/{event_id(event)}.html'


def load_events(root=ROOT, years=None):
    rows = []
    paths = (sorted((root / 'generated').glob('meteor-showers-*.json')) if years is None else
             [root / 'generated' / f'meteor-showers-{year}.json' for year in years])
    for path in paths:
        data = json.loads(path.read_text(encoding='utf-8'))
        for event in data['showers']:
            datetime.fromisoformat(event['utc'].replace('Z', '+00:00'))
            rows.append(event)
    ids = [event_id(e) for e in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate meteor-shower identities')
    return sorted(rows, key=lambda e: (e['utc'], event_id(e)))


def clock(event):
    return datetime.fromisoformat(event['utc'].replace('Z', '+00:00')).strftime('%B %d, %Y at %H:%M:%S UTC')


def render_note(event, highlights=False):
    e = {k: html.escape(str(v)) for k, v in event.items()}
    body = (f"<p>Nominal peak: <time datetime=\"{e['utc']}\">{clock(event)}</time>. "
            f"Radiant in {e['radiant_constellation']}; reference ZHR ≈ {e['expected_zhr']}. "
            f"Moon {e['moon_illumination_percent']}% illuminated at peak.</p>")
    if not highlights:
        body += (f"<p>{e['observing_guidance']}</p>"
                 '<p>The radiant is the direction from which shower meteors appear to spread. '
                 'Watch a broad area of sky. A high radiant, darkness, and a clear sky matter more '
                 'than watching at the exact nominal peak time.</p>')
    return body + '<p>ZHR is an ideal-condition reference rate, not a prediction of how many you will see. Moon interference also depends on whether the Moon is above your horizon.</p>'


def week_notes(page_path, highlights=False, root=ROOT):
    year = int(page_path.parent.parent.name)
    week = int(page_path.parent.name.removeprefix('W'))
    monday = date.fromisocalendar(year, week, 1)
    sunday = monday + timedelta(days=6)
    blocks = []
    # Include adjacent civil years for ISO weeks crossing New Year.
    for event in load_events(root):
        if monday <= date.fromisoformat(event['utc'][:10]) <= sunday:
            blocks.append(f'<section class="sky-note-meteor" data-meteor-id="{event_id(event)}">'
                          f'<h4><a href="{href(event)}">{html.escape(event["name"])} meteor shower</a></h4>'
                          + render_note(event, highlights) + '</section>')
    return '\n'.join(blocks)


def page(title, body):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)} — Star Almanack</title><style>'
            'body{max-width:760px;margin:2rem auto;padding:0 1rem;font:1.12rem/1.65 Georgia,serif;'
            'background:#fffdf8;color:#202833}h1,h2,h3{color:#17344d;line-height:1.2}'
            'a{color:#245c86}li{margin:.6rem 0}dt{font-weight:bold}dd{margin:0 0 1rem}'
            'section{margin:2rem 0}</style></head><body><main>'
            '<nav><a href="/star-almanack/">Star Almanack</a> / '
            '<a href="/almanack/meteors/">Meteor showers</a></nav>'
            f'<h1>{html.escape(title)}</h1>{body}'
            '<footer><h2>Sources and calculation</h2><p>Original explanations and publication calculations: Star Almanack. '
            'Nominal peak solar longitudes, radiant constellations, and reference rates: '
            '<a href="https://www.imo.net/resources/calendar/">International Meteor Organization shower calendar and working list</a>. '
            'Peak longitude crossings and approximate Moon illumination come from our stored calculations using '
            '<a href="https://ssd.jpl.nasa.gov/planets/eph_export.html">JPL/NAIF ephemeris kernels</a>.</p>'
            '<p>A calculated longitude crossing is a nominal seasonal marker, not a forecast of the exact observed maximum. '
            'Shower strength and timing vary between years. Moon illumination alone is not a local visibility calculation.</p></footer>'
            '</main></body></html>')


def render_card(event):
    day = date.fromisoformat(event['utc'][:10])
    year, week, _ = day.isocalendar()
    body = render_note(event)
    body += (f'<h2>Calculated seasonal marker</h2><p>Solar longitude: {event["solar_longitude_deg"]}°. '
             'The published clock retains the calculation’s precision; it does not imply that '
             'the physical shower maximum is known to the second.</p>'
             '<h2>Plan your observing</h2><p>Convert both the date and time from UTC to your local time. '
             'Choose a dark observing period when the radiant is above the horizon; '
             'the nominal peak can occur during your daylight. Meteors can appear away from the radiant. '
             'Use your unaided eyes to cover more sky, dress for the temperature, and give yourself time to watch.</p>'
             f'<p><a href="/almanack/{year}/W{week:02d}/">Open this week in the Almanack</a> · '
             f'<a href="{event_id(event)}.json" download>Download calculation record (JSON)</a></p>')
    return page(f'{event["name"]} · {day.year}', body)


def render_index(events):
    body = ('<p>A meteor is a brief streak of light produced as a small particle enters Earth’s atmosphere. '
            'A shower occurs when Earth crosses a stream of debris. Perspective makes the meteors '
            'appear to spread from one part of the sky: the radiant.</p>'
            '<h2>How to read these cards</h2><p>Each card gives a calculated nominal peak, '
            'radiant constellation, reference rate, Moon illumination, and observing guidance. '
            'The catalog covers ten selected annual showers for each available year; it is not a complete list of meteor showers.</p>'
            '<p>ZHR means zenithal hourly rate: a standardized rate for a radiant overhead in a very dark, clear sky. '
            'Your count is usually lower. The radiant’s altitude, sky brightness, clouds, and Moon position all affect what you see.</p>')
    for year in sorted({e['utc'][:4] for e in events}):
        body += f'<section><h2>{year} meteor showers</h2><ul>'
        for event in events:
            if event['utc'][:4] == year:
                body += (f'<li><a href="{href(event)}">{html.escape(event["name"])}</a> — '
                         f'{clock(event)} · Moon {event["moon_illumination_percent"]}%</li>')
        body += '</ul></section>'
    return page('Meteor showers', body)
