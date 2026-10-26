#!/usr/bin/env python3
"""Generate deterministic J2000 finders using the accepted asterism paths."""
import argparse
import csv
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BG = '#071527'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'star-almanack/chart-library/asterisms')
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    paths = json.loads((ROOT/'asterism-figure-paths.json').read_text())['asterisms']
    figures = json.loads((ROOT/'finder-geometry/martz-macrobert.json').read_text())['constellations']
    stars = []
    with (ROOT/'expanded-bayer-stars.csv').open(newline='', encoding='utf-8') as source:
        for row in csv.DictReader(source):
            try:
                if float(row['mag']) <= 5:
                    stars.append((float(row['ra_h'])*15, float(row['dec_deg']), float(row['mag'])))
            except (ValueError, KeyError):
                continue
    with (ROOT/'asterism-member-coordinates.csv').open(newline='', encoding='utf-8') as source:
        rows = list(csv.DictReader(source))
    # Reuse saved figure vertices and member coordinates to fill out the sky.
    for fig in figures.values():
        for route in fig.get('paths', []):
            for star in route:
                if star.get('magnitude') is not None and float(star['magnitude']) <= 5:
                    stars.append((float(star['ra_h'])*15, float(star['dec_deg']), float(star['magnitude'])))
    stars.extend((float(r['ra_h'])*15,float(r['dec_deg']),float(r['mag'])) for r in rows if float(r['mag']) <= 5)
    stars = list({(round(ra,4), round(dec,4)): (ra,dec,mag) for ra,dec,mag in stars}.values())
    assert len(paths) == 28
    manifest = []
    for name, entry in paths.items():
        pts = {r['member']: (float(r['ra_h'])*15, float(r['dec_deg']), float(r['mag']))
               for r in rows if r['asterism'] == name}
        assert pts, name
        assert all(m in pts for route in entry['paths'] for m in route), name
        angles = [math.radians(v[0]) for v in pts.values()]
        ra0 = math.atan2(sum(math.sin(t) for t in angles), sum(math.cos(t) for t in angles))
        dec0 = math.radians(sum(v[1] for v in pts.values())/len(pts))
        polar = name == 'Little Dipper'
        height = 1000 if polar else 740

        def plane(ra, dec):
            a, d = math.radians(ra), math.radians(dec)
            if polar:
                # An azimuthal polar view is continuous through 0h RA and the pole.
                r = 90-dec
                return -r*math.sin(a), -r*math.cos(a)
            da = (a-ra0+math.pi) % (2*math.pi)-math.pi
            denominator = 1+math.sin(dec0)*math.sin(d)+math.cos(dec0)*math.cos(d)*math.cos(da)
            if denominator < .05:
                return None
            k = 2/denominator
            return (-math.degrees(k*math.cos(d)*math.sin(da)),
                    -math.degrees(k*(math.cos(dec0)*math.sin(d)-math.sin(dec0)*math.cos(d)*math.cos(da))))

        projected = {m: plane(v[0], v[1]) for m, v in pts.items()}
        assert all(v is not None for v in projected.values()), name
        xs, ys = zip(*projected.values())
        if polar:
            scale, mx, my, cy = 420/22.5, 0, 0, 550
        else:
            # A minimum field keeps compact groups legible while showing surroundings.
            field = 2 if name in ('Pleiades', 'Coathanger') else 8
            scale = min(900/max(max(xs)-min(xs), field), 480/max(max(ys)-min(ys), field))
            mx, my, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2, 413

        def project(ra, dec):
            p = plane(ra, dec)
            return None if p is None else (600+(p[0]-mx)*scale, cy+(p[1]-my)*scale)

        def inside(p, margin=0):
            if p is None:
                return False
            x, y = p
            return math.hypot(x-600, y-550) < 420-margin if polar else 24+margin<x<1176-margin and 112+margin<y<714-margin

        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">',
                 f'<rect width="1200" height="{height}" fill="{BG}"/>',
                 f'<text x="600" y="55" text-anchor="middle" font-size="30" fill="#d9efff">{html.escape(name)}</text>',
                 '<text x="600" y="84" text-anchor="middle" font-size="15" fill="#a9c7d9">Star Almanack · J2000.0</text>']
        window = '<circle cx="600" cy="550" r="420"/>' if polar else '<rect x="24" y="112" width="1152" height="602"/>'
        parts += [f'<defs><clipPath id="sky-window">{window}</clipPath></defs>', '<g clip-path="url(#sky-window)">']
        occupied = []
        member_xy = [project(v[0], v[1]) for v in pts.values()]

        def label(text, x, y, size=14, color='#d9efff'):
            w = len(text)*size*.57
            for dx, dy in ((10,-12),(10,22),(-w-10,-12),(-w-10,22),(10,-32),(10,42),(-w-10,-32),(-w-10,42),(10,-52),(10,62),(-w-10,-52),(-w-10,62)):
                box = (x+dx-3,y+dy-size-3,x+dx+w+3,y+dy+4)
                if not all(inside(p, 4) for p in ((box[0],box[1]),(box[2],box[3]))):
                    continue
                if any(box[0]<b[2] and b[0]<box[2] and box[1]<b[3] and b[1]<box[3] for b in occupied):
                    continue
                if any(box[0]-4<s[0]<box[2]+4 and box[1]-4<s[1]<box[3]+4 for s in member_xy):
                    continue
                occupied.append(box)
                parts.append(f'<text x="{x+dx:.2f}" y="{y+dy:.2f}" font-size="{size}" fill="{color}" paint-order="stroke" stroke="{BG}" stroke-width="4">{html.escape(text)}</text>')
                return

        if polar:
            for dec in (70,80):
                parts.append(f'<circle cx="600" cy="550" r="{(90-dec)*scale:.2f}" fill="none" stroke="#24384d" stroke-dasharray="3 6"/>')
            parts.append('<circle cx="600" cy="550" r="2" fill="#adc4dd"/>')
            label('North celestial pole',600,550,12,'#adc4dd')
        for ra, dec, mag in stars:
            p = project(ra, dec)
            if inside(p):
                x, y = p
                parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{max(.75,3.4-.48*mag):.2f}" fill="#aabed0" opacity=".9"/>')
        context_labels = []
        for key, fig in figures.items():
            if not fig.get('has_figure'):
                continue
            visible = []
            for route in fig.get('paths', []):
                for u, v in zip(route, route[1:]):
                    p, q = (project(float(s['ra_h'])*15,float(s['dec_deg'])) for s in (u,v))
                    # Never connect a projection seam or draw a false line through the field.
                    if not p or not q or not (inside(p) or inside(q)):
                        continue
                    if math.dist(p,q) > 1000:
                        continue
                    # The target's accepted paths replace its constellation outline.
                    if (name == 'Little Dipper' and key == 'UMi') or (name == 'Big Dipper' and key == 'UMa'):
                        continue
                    parts.append(f'<line x1="{p[0]:.2f}" y1="{p[1]:.2f}" x2="{q[0]:.2f}" y2="{q[1]:.2f}" stroke="#738ca7" stroke-width="1.4" opacity=".68"/>')
                    visible.extend(s for s in (p,q) if inside(s,25))
            if visible:
                context_labels.append((fig['name'],sum(p[0] for p in visible)/len(visible),sum(p[1] for p in visible)/len(visible)))
        for route in entry['paths']:
            for u, v in zip(route,route[1:]):
                p, q = project(*pts[u][:2]), project(*pts[v][:2])
                parts.append(f'<line class="asterism" x1="{p[0]:.2f}" y1="{p[1]:.2f}" x2="{q[0]:.2f}" y2="{q[1]:.2f}" stroke="#4fc47b" stroke-width="3"/>')
        for member, (ra,dec,mag) in pts.items():
            x,y = project(ra,dec)
            assert inside((x,y),20), (name,member)
            parts.append(f'<circle class="member" cx="{x:.2f}" cy="{y:.2f}" r="{max(2.5,min(7,6.5-mag*.6)):.1f}" fill="#f6f4dc"/>')
            label(member,x,y)
        for text,x,y in context_labels:
            label(text,x,y,15,'#adc4dd')
        parts.extend(['</g>','</svg>'])
        filename = f"asterism-{entry['id']}.svg"
        (output/filename).write_text('\n'.join(parts)+'\n',encoding='utf-8')
        manifest.append({'name':name,'file':filename,'members':len(pts)})
    (output/'manifest.json').write_text(json.dumps({'epoch':'J2000.0','views':manifest},indent=2)+'\n')
    print(f'Generated {len(manifest)} charts in {output}')


if __name__ == '__main__':
    main()
