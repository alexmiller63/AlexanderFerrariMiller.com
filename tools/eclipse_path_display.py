"""Reader-facing plots and coordinate tables for calculated central tracks."""
import html
import json
from datetime import datetime
from eclipse_path import split_track


def central_path_events(event):
    """Pair calculated event times with the nearest stored surface position.

    Rounded axis contacts can fall outside Earth's surface, so never claim
    that the nearest available coordinate is an exact contact position.
    """
    points = event.get('central_path', {}).get('points', [])
    if not points:
        return []
    contacts = event.get('contacts_utc', {})
    if isinstance(contacts, str):
        contacts = json.loads(contacts)
    def instant(value):
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    milestones = [
        ('Central path begins' if contacts.get('axis_entry') else 'First stored point',
         contacts.get('axis_entry') or points[0]['utc']),
        ('Greatest eclipse', event.get('greatest_utc')),
        ('Central path ends' if contacts.get('axis_exit') else 'Last stored point',
         contacts.get('axis_exit') or points[-1]['utc']),
    ]
    result = []
    for label, utc in milestones:
        if not utc:
            continue
        point = min(points, key=lambda p: abs((instant(p['utc']) - instant(utc)).total_seconds()))
        result.append({'label': label, 'utc': utc, 'point': point})
    return result


def render_central_path(event):
    path = event.get('central_path')
    if not path or not path.get('points'):
        return ''
    points = path['points']
    title = 'Calculated central path'
    result = '<section id="eclipse-visibility"><h2>' + title + '</h2>'
    result += ('<p>Star Almanack calculates these coordinates from its Sun–Moon shadow geometry. '
               'The line follows the center of the eclipse track. Total portions are blue; '
               'annular portions are orange. Longitude is positive east.</p>')
    # Equirectangular coordinate plot: no external maps or geographic data.
    def xy(p):
        return 50 + (p['longitude_deg'] + 180) * 2, 30 + (90 - p['latitude_deg']) * 2
    svg = ['<svg viewBox="0 0 820 540" style="display:block;width:100%;height:auto" role="img" aria-labelledby="path-title path-desc" '
           'xmlns="http://www.w3.org/2000/svg"><title id="path-title">Calculated eclipse center line</title>'
           '<desc id="path-desc">Latitude and longitude plot. Blue is total, orange is annular. '
           'The line does not show path width or the wider partial eclipse region.</desc>'
           '<rect x="50" y="30" width="720" height="360" fill="#f0f6fa" stroke="#708090"/>']
    for lon in range(-180, 181, 60):
        x = 50 + (lon + 180) * 2
        svg.append(f'<path d="M{x} 30V390" stroke="#c5ced6"/><text x="{x}" y="412" text-anchor="middle" font-size="13">{lon}°</text>')
    for lat in range(-90, 91, 30):
        y = 30 + (90 - lat) * 2
        svg.append(f'<path d="M50 {y}H770" stroke="#c5ced6"/><text x="43" y="{y+4}" text-anchor="end" font-size="13">{lat}°</text>')
    for segment in split_track(points):
        color = '#195ea8' if segment[-1]['phase'] == 'total' else '#b35400'
        coords = ' '.join(f'{xy(p)[0]:.3f},{xy(p)[1]:.3f}' for p in segment)
        svg.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="3"/>')
    svg.append('<text x="410" y="435" text-anchor="middle" font-size="14">Longitude (east positive)</text>')
    # Labels identify calculated events, rather than arbitrary sample quarters.
    milestones = central_path_events(event)
    for n, milestone in enumerate(milestones):
        p = milestone['point']
        x, y = xy(p)
        tx = 160 + n * 250
        clock = datetime.fromisoformat(milestone['utc'].replace('Z', '+00:00')).strftime('%H:%M:%S UTC')
        stamp = html.escape(milestone['utc'], quote=True)
        label = html.escape(milestone['label'])
        position_stamp = html.escape(p['utc'], quote=True)
        svg.append(f'<line x1="{x:.3f}" y1="{y:.3f}" x2="{tx}" y2="465" stroke="#526c7b" stroke-width="1"/>'
                   f'<circle cx="{x:.3f}" cy="{y:.3f}" r="4" fill="#203747" data-utc="{stamp}"><title>{label}: {stamp}; nearest stored position: {position_stamp}</title></circle>'
                   f'<text x="{tx}" y="487" text-anchor="middle" font-size="15" fill="#203747">{label}</text>'
                   f'<text x="{tx}" y="509" text-anchor="middle" font-size="15" fill="#203747">{clock}</text>')
    svg.append('</svg>')
    result += ''.join(svg)
    result += '<p>Labels give calculated event times; markers use the nearest stored path coordinates. Beginning and ending refer to the central axis crossing Earth, not the global partial-eclipse limits.</p>'
    result += ('<p>This uses a spherical Earth and instantaneous geometric positions. '
               'It does not yet include Earth’s flattening, light-time corrections, path width, '
               'local contact times, or the wider partial-eclipse visibility area. '
               'Future Earth rotation is estimated. Coordinates are model results, '
               'not a precision observing-site boundary.</p>')
    eid = html.escape(event['id'], quote=True)
    result += f'<p><a href="{eid}-path.csv" download>Download coordinates (CSV)</a> · <a href="{eid}-path.geojson" download>Download track (GeoJSON)</a></p>'
    result += (f'<details><summary>All {len(points)} calculated coordinates</summary>'
               '<div class="data-table-scroll"><table><thead><tr><th>UTC</th><th>Latitude</th>'
               '<th>Longitude</th><th>Central phase</th></tr></thead><tbody>')
    from eclipse_editorial import utc_cell
    for p in points:
        result += (f'<tr><td>{utc_cell(p["utc"])}</td><td>{p["latitude_deg"]:.4f}°</td>'
                   f'<td>{p["longitude_deg"]:.4f}°</td><td>{html.escape(p["phase"])}</td></tr>')
    return result + '</tbody></table></div></details></section>'

