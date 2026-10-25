"""Reader-facing plots and coordinate tables for calculated central tracks."""
import html
from datetime import datetime
from eclipse_path import split_track


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
    svg = ['<svg viewBox="0 0 820 510" style="display:block;width:100%;height:auto" role="img" aria-labelledby="path-title path-desc" '
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
    # Place the clocks in a dedicated band so even clustered points have
    # distinct labels. Leaders link each stored UTC instant to its position.
    indices = sorted({round(j * (len(points) - 1) / 4) for j in range(5)})
    for n, i in enumerate(indices):
        p = points[i]
        x, y = xy(p)
        tx = 100 + n * 155
        clock = datetime.fromisoformat(p['utc'].replace('Z', '+00:00')).strftime('%H:%M:%S UTC')
        stamp = html.escape(p['utc'], quote=True)
        svg.append(f'<line x1="{x:.3f}" y1="{y:.3f}" x2="{tx}" y2="465" stroke="#526c7b" stroke-width="1"/>'
                   f'<circle cx="{x:.3f}" cy="{y:.3f}" r="4" fill="#203747" data-utc="{stamp}"><title>{stamp}</title></circle>'
                   f'<text x="{tx}" y="487" text-anchor="middle" font-size="15" fill="#203747">{clock}</text>')
    svg.append('</svg>')
    result += ''.join(svg)
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

