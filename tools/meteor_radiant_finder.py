"""Original radiant finders using accepted, cached stellar geometry.

Nominal peak radiants: IMO 2026 Meteor Shower Calendar, Table 5, page 25.
These are approximate seasonal reference positions, not calculated or drifting
radiants. Keep this source data distinct from our solar-longitude calculations.
"""
import csv
import html
import json
import math
from functools import lru_cache
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from render_stellar_finders import project

SOURCE = 'https://www.imo.net/files/meteor-shower/cal2026.pdf'
RADIANTS = {
    'Quadrantids': (230, 49), 'Lyrids': (271, 34),
    'η-Aquariids': (338, -1), 'Southern δ-Aquariids': (340, -16),
    'α-Capricornids': (307, -10), 'Perseids': (48, 58),
    'Orionids': (95, 16), 'Leonids': (152, 22),
    'Geminids': (112, 33), 'Ursids': (217, 76),
}


@lru_cache(maxsize=1)
def sources():
    registry = json.loads((ROOT / 'finder-geometry/martz-macrobert.json').read_text())
    stars = {}
    figures = []
    asterisms = []
    for category, output in [('constellations', figures), ('asterisms', asterisms)]:
        for key, record in registry[category].items():
            if category == 'asterisms' and record.get('geometry_status') != 'accepted-paths':
                continue
            paths = record.get('paths', [])
            for path in paths:
                for vertex in path:
                    if vertex.get('ra_h') is None or vertex.get('dec_deg') is None:
                        raise ValueError(f'Missing accepted figure coordinates: {key}')
                    stars.setdefault(str(vertex['id']), vertex)
            if paths:
                output.append((record['name'], paths))
    with (ROOT / 'expanded-bayer-stars.csv').open(newline='', encoding='utf-8-sig') as handle:
        labels = {r['hip']: r for r in csv.DictReader(handle) if r['hip']}
    return stars, figures, asterisms, labels


def render(event):
    ra, dec = RADIANTS[event['name']]
    stars, figures, asterisms, labels = sources()
    def xy(ra_deg, dec_deg):
        p = project(ra_deg, dec_deg, ra, dec)
        return None if p is None else (500-p[0]*420/36, 400-p[1]*285/27)
    def vertex_xy(v):
        return xy(float(v['ra_h'])*15, float(v['dec_deg']))
    def inside(p):
        return p is not None and 80 <= p[0] <= 920 and 115 <= p[1] <= 685
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 870" role="img" aria-labelledby="title desc">',
           f'<title id="title">{html.escape(event["name"])} radiant finder</title>',
           '<desc id="desc">North up, east left. Yellow open circle: nominal peak radiant. Blue constellation figures and green asterisms use accepted Star Almanack geometry. Reference stars are magnitude-scaled.</desc>',
           '<rect width="1000" height="870" fill="#071423"/>',
           '<defs><clipPath id="field"><rect x="80" y="115" width="840" height="570"/></clipPath></defs>',
           '<style>text{font-family:DejaVu Sans,sans-serif;fill:#f3f5f7}</style>']
    def text(x,y,value,size=15,extra=''):
        out.append(f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size}" {extra}>{html.escape(str(value))}</text>')
    def line(a,b,color,width=1):
        out.append(f'<path d="M{a[0]:.3f},{a[1]:.3f} L{b[0]:.3f},{b[1]:.3f}" fill="none" stroke="{color}" stroke-width="{width}"/>')
    text(50,43,event['name']+' · radiant finder',27)
    text(50,76,f'Nominal peak position: RA {ra}° · Dec {dec:+}° · north up, east left',16)
    out.append('<g clip-path="url(#field)">')
    # Sky-coordinate grid, including wraparound RA and the polar region.
    for meridian in range(0,360,30):
        previous=None
        for d in range(-89,90):
            p=xy(meridian,d)
            if p and previous and math.dist(p,previous)<100:
                line(previous,p,'#263b50',.7)
            previous=p
    for parallel in range(-75,90,15):
        previous=None
        for a in range(361):
            p=xy(a,parallel)
            if p and previous and math.dist(p,previous)<100:
                line(previous,p,'#263b50',.7)
            previous=p
    visible_figures=[]
    for name,paths in figures:
        visible=[]
        for path in paths:
            pts=[vertex_xy(v) for v in path]
            visible.extend(p for p in pts if inside(p))
            for a,b in zip(pts,pts[1:]):
                if a and b and math.dist(a,b)<700:
                    line(a,b,'#5c8fe8',1.5)
        if len(visible)>=3:
            visible_figures.append((name,visible))
    for name,paths in asterisms:
        pts=[vertex_xy(v) for path in paths for v in path]
        # Only show an orienting asterism when its whole accepted shape fits.
        if pts and all(inside(p) for p in pts):
            for path in paths:
                for a,b in zip(path,path[1:]):
                    line(vertex_xy(a),vertex_xy(b),'#59c86d',2)
    for hip,v in stars.items():
        p=vertex_xy(v)
        if not inside(p):continue
        magnitude=v.get('magnitude')
        radius=2 if magnitude is None else max(.8,5.5*.70**float(magnitude))
        out.append(f'<circle data-hip="{hip}" cx="{p[0]:.3f}" cy="{p[1]:.3f}" r="{radius:.3f}" fill="#f7f7f2"/>')
    out.append('</g>')
    out.append('<rect x="80" y="115" width="840" height="570" fill="none" stroke="#c4ccd8"/>')
    # Reserve the radiant label and place star labels in clear space.
    occupied=[(475,370,690,430)]
    def place(p,label,color='#f3f5f7',size=14):
        width=len(label)*size*.59
        for dx,dy in [(9,-9),(9,22),(-width-16,-9),(-width-16,22),(9,-28),(9,40),(-width-16,40)]:
            x,y=p[0]+dx,p[1]+dy
            box=(x-3,y-size-2,x+width+3,y+4)
            if box[0]<82 or box[2]>918 or box[1]<117 or box[3]>683:continue
            if any(not(box[2]<b[0] or box[0]>b[2] or box[3]<b[1] or box[1]>b[3]) for b in occupied):continue
            out.append(f'<rect x="{box[0]:.3f}" y="{box[1]:.3f}" width="{box[2]-box[0]:.3f}" height="{box[3]-box[1]:.3f}" fill="#071423"/>')
            text(x,y,label,size,f'style="fill:{color}"')
            occupied.append(box)
            return True
        return False
    guides=[]
    # Prefer a few local landmarks, then add bright stars across the field.
    nearby = sorted(labels.items(), key=lambda kv: math.dist(
        xy(float(kv[1]['ra_h'])*15,float(kv[1]['dec_deg'])) or (1e9,1e9), (500,400)))
    ordered = nearby[:3] + sorted(labels.items(),key=lambda kv:float(kv[1]['mag']))
    used = set()
    for hip,r in ordered:
        if hip in used:continue
        used.add(hip)
        p=xy(float(r['ra_h'])*15,float(r['dec_deg']))
        if not inside(p) or hip not in stars:continue
        label=r['bayer']+(' · '+r['proper'] if r['proper'] else '')
        if place(p,label):guides.append(label)
        if len(guides)>=8:break
    for name,pts in sorted(visible_figures,key=lambda row:-len(row[1])):
        p=(sum(v[0] for v in pts)/len(pts),sum(v[1] for v in pts)/len(pts))
        place(p,name,'#89acf1',16)
    out.append(f'<circle id="radiant" data-ra-deg="{ra}" data-dec-deg="{dec}" cx="500" cy="400" r="11" fill="none" stroke="#ffd84d" stroke-width="2.6"/>')
    out.append('<rect x="519" y="377" width="165" height="45" fill="#071423"/>')
    text(525,395,'Nominal radiant',17,'style="fill:#ffd84d"')
    text(525,415,'near maximum',14,'style="fill:#ffd84d"')
    text(500,104,'N',17,'text-anchor="middle"')
    text(58,405,'E',17)
    text(934,405,'W',17)
    text(500,710,'S',17,'text-anchor="middle"')
    line((95,731),(95+420*10/36,731),'#f3f5f7',2)
    text(95,755,'10° near chart center',14)
    text(50,794,'Yellow: nominal radiant · blue: constellations · green: orienting asterisms',16)
    text(50,821,'Star Almanack chart · IMO nominal peak coordinates · accepted HYG/Hipparcos figure stars',14)
    text(50,846,'Radiant drifts through the shower; orientation is celestial, not a local horizon view.',14)
    return ''.join(out)+'</svg>'
