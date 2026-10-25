"""Original SVG cross-sections derived solely from Star Almanack catalog geometry.

No artwork, eclipse predictions, or geographic outlines are fetched. The
catalog stores unsigned axis distances, so the displacement is drawn to the
right without claiming a celestial orientation or a direction of motion.
"""
import html
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eclipse_engine import EARTH_RADIUS_KM, MOON_RADIUS_KM


def circles(event):
    """Return label, center-x and radius in km, plus fill, back to front."""
    distance = float(event['axis_distance_km'])
    core = float(event['core_radius_km'])
    margin = float(event['penumbra_margin_km'])
    lunar = event['kind'] == 'lunar'
    body_radius = MOON_RADIUS_KM if lunar else EARTH_RADIUS_KM
    penumbra = distance - body_radius - margin
    if not all(math.isfinite(x) for x in (distance, core, penumbra)) or distance < 0 or penumbra <= 0:
        raise ValueError('Invalid eclipse artwork geometry')
    if lunar:
        return [('Penumbra', 0., penumbra, '#ded9ce'),
                ('Umbra', 0., core, '#51485d'),
                ('Moon', distance, body_radius, '#eebd69')]
    return [('Earth section', distance, body_radius, '#96c9db'),
            ('Penumbra', 0., penumbra, '#ded9ce'),
            ('Umbra' if core >= 0 else 'Antumbra', 0., abs(core), '#51485d')]


def svg(event):
    shapes = circles(event)
    if event['kind'] == 'lunar':
        from lunar_eclipse_chart import chart
        return chart(event)
    left = min(x-r for _, x, r, _ in shapes)
    right = max(x+r for _, x, r, _ in shapes)
    height = max(r for _, _, r, _ in shapes)
    scale = min(620 / (right-left), 310 / (2*height))
    center = (left+right)/2
    heading = html.escape(f"{event['date_utc']} · {event['type'].capitalize()} {event['kind']} eclipse")
    elements = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 530" role="img" aria-labelledby="art-title art-desc">',
        f'<title id="art-title">{heading}</title>',
        '<desc id="art-desc">To-scale cross-section at greatest eclipse. '
        'Axis displacement is drawn horizontally; celestial orientation and motion are not represented.</desc>',
        '<rect width="760" height="530" rx="16" fill="#f5f1e8"/>',
        f'<text x="32" y="38" font-size="21" fill="#17344d">{heading}</text>',
        '<text x="32" y="67" font-size="16" fill="#403d48">Shadow geometry at greatest eclipse · distances to scale</text>',
    ]
    for label, x, radius, fill in shapes:
        if radius < 0:
            raise ValueError('Negative radius')
        elements.append(f'<circle data-label="{label}" cx="{380+(x-center)*scale:.4f}" cy="255" r="{radius*scale:.4f}" fill="{fill}" fill-opacity="0.8" stroke="#403d48"/>')
    for i, (label, _, radius, fill) in enumerate(shapes):
        y = 442+i*25
        elements.append(f'<rect x="32" y="{y-12}" width="13" height="13" fill="{fill}" stroke="#403d48"/><text x="55" y="{y}" font-size="16" fill="#403d48">{label} · radius {radius:,.1f} km</text>')
    elements.append('</svg>')
    return ''.join(elements)


def render_artwork(event):
    eid = html.escape(event['id'], quote=True)
    if event['kind'] == 'lunar':
        return ('<section id="lunar-event-chart"><h2>Calculated lunar eclipse chart</h2>'
                f'<p><a href="{eid}-shadow.svg">Open the full-resolution chart for detailed study</a></p>'
                f'<figure style="margin:0"><a href="{eid}-shadow.svg"><img src="{eid}-shadow.svg" '
                'style="width:100%;height:auto" alt="Detailed calculated lunar eclipse chart: track, contact positions, timing, geometry and geographic horizon maps"></a>'
                '<figcaption>The full event in one chart. North is celestial north and east is left. '
                'The maps show the geometric Moon-center horizon at three instants, rather than whole-event visibility. '
                'Open or download the SVG to enlarge its labels and inspect the calculations.</figcaption></figure>'
                f'<p><a href="{eid}-contacts.csv" download>Contact coordinates (CSV)</a> · '
                f'<a href="{eid}-chart.json" download>Complete chart measurements (JSON)</a></p>'
                '<p>Original chart and calculations by Star Almanack; positional input from the credited JPL kernel. '
                'Model assumptions and limitations appear on the chart.</p></section>')
    description = (
        'Earth’s shadow at the Moon’s projected distance. The Moon is shown at greatest eclipse.'
        if event['kind'] == 'lunar' else
        'Earth and the shadow cones in the plane of closest shadow-axis approach to Earth’s center. '
        'This is a geometric cross-section, not a map of the ground shadow or a view of the Sun.')
    return ('<section><h2>Our calculated shadow diagram</h2>'
            f'<figure style="margin:0"><img src="{eid}-shadow.svg" '
            'style="width:100%;height:auto" alt="Calculated eclipse shadow cross-section">'
            f'<figcaption>{description} Displacement is drawn horizontally because the stored '
            'record gives distance from the axis, without sky orientation. This does not '
            'show the Moon’s track, surface features, or geographic visibility.</figcaption></figure>'
            f'<p><a href="{eid}-shadow.svg">Open original SVG diagram</a></p>'
            '<p>Artwork generated by Star Almanack from its stored shadow geometry; '
            'Sun, Earth, and Moon positions use the credited JPL kernel.</p></section>')
