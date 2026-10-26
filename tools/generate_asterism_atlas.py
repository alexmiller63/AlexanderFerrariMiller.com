#!/usr/bin/env python3
"""Generate deterministic J2000 finders using the accepted asterism paths."""
import argparse
import csv
import html
import json
import math
from sky_optional_layers import load_layers
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BG = '#071527'
DETAIL_VIEWS = {'Pleiades', 'Teapot of Sagittarius'}
# Accepted lower detail panels from the reviewed atlas. Scale is relative to
# the displayed wide-view coordinates, rounded to the same hundredth pixel.
LOWER_DETAILS = {'Coathanger': (30, 1000, 430, 1250),
                 "Job's Coffin": (10, 1020, 470, 1290),
                 "Orion's Sword": (18, 1040, 500, 1320)}
# Compact patterns need their host figure even when none of its vertices are members.
HOST_OVERRIDES = {'Pleiades': ['Tau'], 'Coathanger': ['Vul']}



def segment_hits_box(a, b, box):
    """Liang–Barsky intersection, including segments crossing the whole box."""
    x0,y0=a; dx=b[0]-x0; dy=b[1]-y0
    lo,hi=0.,1.
    for p,q in ((-dx,x0-box[0]),(dx,box[2]-x0),(-dy,y0-box[1]),(dy,box[3]-y0)):
        if abs(p)<1e-12:
            if q<0:return False
        elif p<0:lo=max(lo,q/p)
        else:hi=min(hi,q/p)
        if lo>hi:return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'star-almanack/chart-library/asterisms')
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    paths = json.loads((ROOT/'asterism-figure-paths.json').read_text())['asterisms']
    figures = json.loads((ROOT/'finder-geometry/martz-macrobert.json').read_text())['constellations']
    stars = []
    with (ROOT/'expanded-bayer-stars.csv').open(newline='', encoding='utf-8') as source:
        for row in csv.DictReader(source):
            try:
                if float(row['mag']) <= 5:
                    stars.append((float(row['ra_h'])*15, float(row['dec_deg']), float(row['mag']), row.get('proper') or row.get('bayer', '')))
            except (ValueError, KeyError):
                continue
    with (ROOT/'asterism-member-coordinates.csv').open(newline='', encoding='utf-8') as source:
        rows = list(csv.DictReader(source))
    # Reuse saved figure vertices and member coordinates to fill out the sky.
    for fig in figures.values():
        for route in fig.get('paths', []):
            for star in route:
                if star.get('magnitude') is not None and float(star['magnitude']) <= 5:
                    stars.append((float(star['ra_h'])*15, float(star['dec_deg']), float(star['magnitude']), ''))
    stars.extend((float(r['ra_h'])*15,float(r['dec_deg']),float(r['mag']), '') for r in rows if float(r['mag']) <= 5)
    merged = {}
    for ra, dec, mag, label_name in stars:
        key = (round(ra, 4), round(dec, 4))
        old = merged.get(key)
        merged[key] = (ra, dec, mag, label_name or (old[3] if old else ''))
    stars = list(merged.values())
    assert len(paths) == 28
    annotate, boundaries = load_layers()
    manifest = []
    chart_html = []
    for name, entry in paths.items():
        pts = {r['member']: (float(r['ra_h'])*15, float(r['dec_deg']), float(r['mag']))
               for r in rows if r['asterism'] == name}
        assert pts, name
        assert all(m in pts for route in entry['paths'] for m in route), name
        angles = [math.radians(v[0]) for v in pts.values()]
        ra0 = math.atan2(sum(math.sin(t) for t in angles), sum(math.cos(t) for t in angles))
        dec0 = math.radians(sum(v[1] for v in pts.values())/len(pts))
        polar = name == 'Little Dipper'
        height = LOWER_DETAILS[name][3] if name in LOWER_DETAILS else 1000 if polar else 740
        inset = name in DETAIL_VIEWS

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
            scale, mx, my, cy = 420/50, 0, 0, 550
        else:
            # Preserve the projection and accepted target paths; fit the complete
            # host figure, then add room for neighboring constellations.
            frame = list(projected.values())
            hosts = set(HOST_OVERRIDES.get(name, []))
            for key, fig in figures.items():
                if any(abs(float(v['dec_deg'])-dec) < .03 and
                       abs((float(v['ra_h'])*15-ra+180)%360-180) < .03
                       for route in fig.get('paths', []) for v in route
                       for ra, dec, _ in pts.values()):
                    hosts.add(key)
            for key in hosts:
                for route in figures[key].get('paths', []):
                    frame.extend(p for v in route
                                 if (p := plane(float(v['ra_h'])*15, float(v['dec_deg']))) is not None)
            fx, fy = zip(*frame)
            scale = min(900/max((max(fx)-min(fx))*1.6, 40),
                        480/max((max(fy)-min(fy))*1.6, 32))
            mx, my, cy = (min(fx)+max(fx))/2, (min(fy)+max(fy))/2, 413

        def project(ra, dec):
            p = plane(ra, dec)
            return None if p is None else (600+(p[0]-mx)*scale, cy+(p[1]-my)*scale)

        def inside(p, margin=0):
            if p is None:
                return False
            x, y = p
            return math.hypot(x-600, y-550) < 420-margin if polar else 24+margin<x<1176-margin and 112+margin<y<714-margin

        canvas_width = 1760 if inset else 1200
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{height}" viewBox="0 0 {canvas_width} {height}">',
                 f'<rect width="{canvas_width}" height="{height}" fill="{BG}"/>',
                 f'<text x="600" y="55" text-anchor="middle" font-size="30" fill="#d9efff">{html.escape(name)}</text>',
                 '<text x="600" y="84" text-anchor="middle" font-size="15" fill="#a9c7d9">Star Almanack · J2000.0</text>']
        window = '<circle cx="600" cy="550" r="420"/>' if polar else '<rect x="24" y="112" width="1152" height="602"/>'
        parts += [f'<defs><clipPath id="sky-window">{window}</clipPath></defs>', '<g clip-path="url(#sky-window)">']
        occupied = []
        target_segments = []
        member_xy = [project(v[0], v[1]) for v in pts.values()]

        def label(text, x, y, size=14, color='#d9efff'):
            w = len(text)*size*.57
            for dx, dy in [(dx, dy) for dy in (-12,22,-32,42,-52,62,-82,92,-112,122)
                           for dx in (10,-w-10,-w/2,45,-w-45)]:
                box = (x+dx-3,y+dy-size-3,x+dx+w+3,y+dy+4)
                if not all(inside(p, 4) for p in ((box[0],box[1]),(box[2],box[3]))):
                    continue
                if any(box[0]<b[2] and b[0]<box[2] and box[1]<b[3] and b[1]<box[3] for b in occupied):
                    continue
                if any(box[0]-4<s[0]<box[2]+4 and box[1]-4<s[1]<box[3]+4 for s in member_xy):
                    continue
                # Keep labels off the green target, including its handle and bowl.
                if any(segment_hits_box(a, b, box) for a, b in target_segments):
                    continue
                occupied.append(box)
                parts.append(f'<text x="{x+dx:.2f}" y="{y+dy:.2f}" font-size="{size}" fill="{color}" paint-order="stroke" stroke="{BG}" stroke-width="4">{html.escape(text)}</text>')
                return

        if polar:
            for dec in (40,50,60,70,80):
                parts.append(f'<circle cx="600" cy="550" r="{(90-dec)*scale:.2f}" fill="none" stroke="#24384d" stroke-dasharray="3 6"/>')
            parts.append('<circle cx="600" cy="550" r="2" fill="#adc4dd"/>')
            label('North celestial pole',600,550,12,'#adc4dd')
        for ra, dec, mag, star_name in stars:
            p = project(ra, dec)
            if inside(p):
                x, y = p
                parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{max(.75,3.4-.48*mag):.2f}" fill="#aabed0" opacity=".9"/>')
        accepted_segments = [(project(*pts[u][:2]), project(*pts[v][:2]))
                             for route in entry['paths'] for u,v in zip(route,route[1:])]
        target_segments.extend(accepted_segments)
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
                    # The older constellation registry has alternate bowl chords.
                    # Keep those out of the corrected Dippers, while retaining
                    # all host segments extending beyond the asterism members.
                    if name in ('Big Dipper', 'Little Dipper') and all(
                            any(math.dist(endpoint,m)<.1 for m in member_xy)
                            for endpoint in (p,q)):
                        visible.extend(s for s in (p,q) if inside(s,25))
                        continue
                    # Omit only a constellation segment identical to a green
                    # target segment, keeping the rest of its host figure.
                    if any((math.dist(p,a)<.1 and math.dist(q,b)<.1) or
                           (math.dist(p,b)<.1 and math.dist(q,a)<.1)
                           for a,b in accepted_segments):
                        visible.extend(s for s in (p,q) if inside(s,25))
                        continue
                    parts.append(f'<line x1="{p[0]:.2f}" y1="{p[1]:.2f}" x2="{q[0]:.2f}" y2="{q[1]:.2f}" stroke="#5c8fe8" stroke-width="1.4" opacity=".68"/>')
                    visible.extend(s for s in (p,q) if inside(s,25))
            if visible:
                # Anchor to the visible figure, not a centroid that may sit
                # on an unrelated foreground asterism (notably Draco).
                center = (sum(p[0] for p in visible)/len(visible), sum(p[1] for p in visible)/len(visible))
                anchor = min(visible, key=lambda p: math.dist(p, center))
                context_labels.append((fig['name'], *anchor))
        for route in entry['paths']:
            for u, v in zip(route,route[1:]):
                p, q = project(*pts[u][:2]), project(*pts[v][:2])
                parts.append(f'<line class="asterism" x1="{p[0]:.2f}" y1="{p[1]:.2f}" x2="{q[0]:.2f}" y2="{q[1]:.2f}" stroke="#4fc47b" stroke-width="3"/>')
        for member, (ra,dec,mag) in pts.items():
            x,y = project(ra,dec)
            assert inside((x,y),20), (name,member)
            parts.append(f'<circle class="member" cx="{x:.2f}" cy="{y:.2f}" r="{max(2.5,min(7,6.5-mag*.6)):.1f}" fill="#f6f4dc"/>')
            if not inset:
                label(member,x,y)
        if inset:
            label(name + ' → detail', sum(p[0] for p in member_xy)/len(member_xy),
                  sum(p[1] for p in member_xy)/len(member_xy), 14, '#69dc94')
        for text,x,y in context_labels:
            label(text,x,y,15,'#92b8ff')
        for ra, dec, mag, star_name in sorted(stars, key=lambda s:s[2]):
            p = project(ra,dec)
            if star_name and mag <= 3 and inside(p,25) and all(math.dist(p,q)>8 for q in member_xy):
                label(star_name,*p,12,'#b8cddd')
        base = '\n'.join(parts)
        overlay, _ = annotate(base, project, lambda x,y,m=0: inside((x,y),m), name)
        parts.append(overlay)
        boundary_layer = ['<g class="constellation-boundaries" fill="none" stroke="#d0d6de" opacity=".48">']
        for a,b in boundaries:
            u,v = project(*a),project(*b)
            if u and v and math.dist(u,v)<1000 and (inside(u) or inside(v)):
                boundary_layer.append(f'<path d="M{u[0]:.2f},{u[1]:.2f}L{v[0]:.2f},{v[1]:.2f}"/>')
        boundary_layer.append('</g>')
        # Insert behind the stars and the accepted figure.
        parts.insert(6, ''.join(boundary_layer))
        parts.append('</g>')
        if polar:
            parts.append('<circle cx="600" cy="550" r="420" fill="none" stroke="#92b8ff"/>')
        if inset:
            # A separate detail panel cannot obscure the wide context view.
            ix, iy, iw, ih = 1220, 145, 510, 480
            detail_scale = min((iw-100)/max(max(xs)-min(xs),.1),
                               (ih-140)/max(max(ys)-min(ys),.1))
            dx0, dy0 = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
            def detail_point(member):
                x,y = projected[member]
                return ix+iw/2+(x-dx0)*detail_scale, iy+ih/2+25+(y-dy0)*detail_scale
            parts.extend([f'<g id="detail-inset"><rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" rx="8" fill="{BG}" stroke="#7290ac"/>',
                          f'<text x="{ix+iw/2}" y="{iy+32}" text-anchor="middle" font-size="20" fill="#d9efff">Detail · {html.escape(name)}</text>'])
            for route in entry['paths']:
                for u,v in zip(route,route[1:]):
                    a,b = detail_point(u),detail_point(v)
                    parts.append(f'<line class="asterism-detail" x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="#4fc47b" stroke-width="3"/>')
            # Use the same label collision rules within the inset's own window.
            saved_inside, saved_members, saved_segments = inside, member_xy, target_segments
            def inside(p,margin=0):
                return p is not None and ix+margin<p[0]<ix+iw-margin and iy+50+margin<p[1]<iy+ih-margin
            member_xy = [detail_point(m) for m in pts]
            target_segments = [(detail_point(u),detail_point(v)) for route in entry['paths'] for u,v in zip(route,route[1:])]
            for member, (_,_,mag) in pts.items():
                x,y = detail_point(member)
                parts.append(f'<circle class="member-detail" cx="{x:.2f}" cy="{y:.2f}" r="{max(2.5,min(7,6.5-mag*.6)):.1f}" fill="#f6f4dc"/>')
                label(member,x,y,12)
            def detail_project(ra,dec):
                pt = plane(ra,dec)
                return None if pt is None else (ix+iw/2+(pt[0]-dx0)*detail_scale, iy+ih/2+25+(pt[1]-dy0)*detail_scale)
            overlay, _ = annotate('\n'.join(parts), detail_project, lambda x,y,m=0: inside((x,y),m), name+' detail')
            parts.append(overlay)
            parts.append(f'<defs><clipPath id="detail-window"><rect x="{ix}" y="{iy+50}" width="{iw}" height="{ih-50}"/></clipPath></defs>')
            parts.append('<g class="constellation-boundaries" clip-path="url(#detail-window)" fill="none" stroke="#d0d6de" opacity=".48">')
            for a,b in boundaries:
                u,v=detail_project(*a),detail_project(*b)
                if u and v and math.dist(u,v)<1000 and (inside(u) or inside(v)):
                    parts.append(f'<path d="M{u[0]:.2f},{u[1]:.2f}L{v[0]:.2f},{v[1]:.2f}"/>')
            parts.append('</g>')
            inside, member_xy, target_segments = saved_inside, saved_members, saved_segments
            parts.append('</g>')
            parts.append(f'<text x="{ix+iw/2}" y="{iy+ih+28}" text-anchor="middle" font-size="14" fill="#a9c7d9">Same accepted star pattern · enlarged</text>')
        if name in LOWER_DETAILS:
            factor, center_y, panel_height, _ = LOWER_DETAILS[name]
            wide = {m: tuple(round(c, 2) for c in project(*pt[:2])) for m,pt in pts.items()}
            wx,wy = zip(*wide.values())
            center_x0,center_y0 = (min(wx)+max(wx))/2,(min(wy)+max(wy))/2
            def lower_point(member):
                x,y=wide[member]
                return 600+(x-center_x0)*factor,center_y+(y-center_y0)*factor
            def lower_project(ra,dec):
                p=project(ra,dec)
                return None if p is None else (600+(p[0]-center_x0)*factor,center_y+(p[1]-center_y0)*factor)
            def lower_inside(p,margin=0):
                return p is not None and 80+margin<p[0]<1120-margin and 835+margin<p[1]<780+panel_height-margin
            parts.append(f'<g id="lower-detail-{entry["id"]}"><rect x="80" y="780" width="1040" height="{panel_height}" rx="8" fill="{BG}" stroke="#7290ac"/><text x="600" y="820" text-anchor="middle" font-size="26" fill="#d9efff">{html.escape(name)} · enlarged detail</text>')
            for route in entry['paths']:
                for u,v in zip(route,route[1:]):
                    a,b=lower_point(u),lower_point(v)
                    parts.append(f'<line class="asterism" x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="#4fc47b" stroke-width="3"/>')
            saved_inside,saved_members,saved_segments=inside,member_xy,target_segments
            inside=lower_inside
            member_xy=[lower_point(m) for m in pts]
            target_segments=[(lower_point(u),lower_point(v)) for route in entry['paths'] for u,v in zip(route,route[1:])]
            for member in pts:
                x,y=lower_point(member)
                parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="#f6f4dc"/>')
                label(member,x,y,17)
            overlay,_=annotate('\n'.join(parts),lower_project,lambda x,y,m=0:lower_inside((x,y),m),name+' detail')
            parts.append(overlay)
            parts.append(f'<defs><clipPath id="lower-window-{entry["id"]}"><rect x="80" y="835" width="1040" height="{panel_height-55}"/></clipPath></defs>')
            parts.append(f'<g class="constellation-boundaries" clip-path="url(#lower-window-{entry["id"]})" fill="none" stroke="#d0d6de" opacity=".48">')
            for a,b in boundaries:
                u,v=lower_project(*a),lower_project(*b)
                if u and v and math.dist(u,v)<1000 and (lower_inside(u) or lower_inside(v)):
                    parts.append(f'<path d="M{u[0]:.2f},{u[1]:.2f}L{v[0]:.2f},{v[1]:.2f}"/>')
            parts.append('</g></g>')
            inside,member_xy,target_segments=saved_inside,saved_members,saved_segments
        parts.append('</svg>')
        filename = f"asterism-{entry['id']}.svg"
        svg='\n'.join(parts)
        # Unique clip IDs keep inline charts isolated.
        svg=svg.replace('sky-window', f'sky-window-{entry["id"]}').replace('detail-window',f'detail-window-{entry["id"]}')
        chart_html.append(f'<figure id="view-{len(manifest)}"><h2>{html.escape(name)}</h2>'+svg+'</figure>')
        (output/filename).write_text('\n'.join(parts)+'\n',encoding='utf-8')
        manifest.append({'name':name,'file':filename,'members':len(pts)})
    (output/'manifest.json').write_text(json.dumps({'epoch':'J2000.0','views':manifest},indent=2)+'\n')
    controls='<label><input aria-controls="asterism-charts" id="catalog-toggle" type="checkbox"> Show catalog objects</label> <label><input aria-controls="asterism-charts" id="boundaries-toggle" type="checkbox"> Show constellation boundaries</label>'
    css='body{background:#071527;color:#d9efff;font:16px system-ui;margin:0}main{padding:20px}a{color:#d9efff}label{display:inline-block;padding:12px}svg{width:100%;height:auto}.catalog-objects,.constellation-boundaries{display:none}body:has(#catalog-toggle:checked) .catalog-objects,body:has(#boundaries-toggle:checked) .constellation-boundaries{display:inline}figure{display:none;margin:0}figure:target{display:block}body:not(:has(figure:target)) #view-0{display:block}.chart-list{display:flex;flex-wrap:wrap;gap:12px;padding:16px 0}'
    links=''.join(f'<a href="#view-{i}">{html.escape(v["name"])}</a>' for i,v in enumerate(manifest))
    (output/'index.html').write_text('---\nlayout: null\n---\n<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Asterism Atlas · Star Almanack</title><link rel="stylesheet" href="../../css/star-almanack-nav-20261022.css"><style>'+css+'</style><body>{% include star-almanack-nav.html %}<main id="asterism-charts"><a href="../">← Chart Library</a><h1>Asterism Atlas</h1><p>Green: target asterism · Blue: surrounding constellations · Amber: optional catalog objects · Muted white: optional IAU boundaries · J2000.0</p>'+controls+'<details><summary>Choose an asterism</summary><nav class="chart-list">'+links+'</nav></details>'+''.join(chart_html)+'</main>{% include star-almanack-footer.html %}</body></html>')
    print(f'Generated {len(manifest)} charts in {output}')


if __name__ == '__main__':
    main()
