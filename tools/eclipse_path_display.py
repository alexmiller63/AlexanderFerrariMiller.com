"""Reader-facing event markers and coordinate tables for calculated central tracks."""
import html
import json
from datetime import datetime


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
    title = 'Calculated central path coordinates'
    result = '<section id="eclipse-visibility"><h2>' + title + '</h2>'
    result += ('<p>The central path appears in the study chart above. '
               'Star Almanack calculates these coordinates from its Sun–Moon shadow geometry. '
               'Longitude is positive east.</p>')
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

