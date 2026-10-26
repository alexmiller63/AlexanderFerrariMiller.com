#!/usr/bin/env python3
"""Generate six March-equinox horizon panoramas from local Star Almanack stars.

Standalone standard-library SVG generator. Seasonal event is calculated from
apparent solar longitude; sidereal orientation is derived from 21h apparent
solar time (Sun hour angle +9h), not a civil clock approximation.
"""
import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATITUDES = (75, 45, 15, -15, -45, -75)
SIZE = 900
RADIUS = 360
CX = CY = SIZE / 2

def solar_longitude(t):
    jd = (t - dt.datetime(2000, 1, 1, 12)).total_seconds() / 86400 + 2451545
    T = (jd - 2451545) / 36525
    L = (280.46646 + T * (36000.76983 + .0003032 * T)) % 360
    M = math.radians((357.52911 + T * (35999.05029 - .0001537 * T)) % 360)
    C = (1.914602 - T * (.004817 + .000014 * T)) * math.sin(M) + (.019993 - .000101 * T) * math.sin(2*M) + .000289 * math.sin(3*M)
    omega = math.radians(125.04 - 1934.136 * T)
    return (L + C - .00569 - .00478 * math.sin(omega)) % 360

def equinox(year):
    lo, hi = dt.datetime(year, 3, 18), dt.datetime(year, 3, 23)
    for _ in range(55):
        mid = lo + (hi - lo) / 2
        if solar_longitude(mid) > 180: lo = mid
        else: hi = mid
    return lo + (hi - lo) / 2

def sun_ra(lon):
    eps = math.radians(23.4393)
    l = math.radians(lon)
    return math.atan2(math.cos(eps) * math.sin(l), math.cos(l))

def project(ra, dec, lat, lst):
    h = lst - ra
    phi = math.radians(lat)
    altitude = math.asin(max(-1, min(1, math.sin(phi)*math.sin(dec)+math.cos(phi)*math.cos(dec)*math.cos(h))))
    if altitude < 0: return None
    east = -math.cos(dec)*math.sin(h)
    north = math.sin(dec)*math.cos(phi)-math.cos(dec)*math.cos(h)*math.sin(phi)
    az = math.atan2(east, north)
    radius = RADIUS * (math.pi/2 - altitude)/(math.pi/2)
    return (CX + radius*math.sin(az), CY-radius*math.cos(az))

def svg_poly(points, color, width=1.1, dash=''):
    chunks = []
    segment = []
    def flush():
        if len(segment)>1:
            chunks.append('<polyline points="'+ ' '.join(f'{x:.1f},{y:.1f}' for x,y in segment)+'" fill="none" stroke="'+color+'" stroke-width="'+str(width)+'"'+ (' stroke-dasharray="'+dash+'"' if dash else '')+'/>')
    for point in points:
        if point is None:
            flush(); segment=[]
        else: segment.append(point)
    flush()
    return ''.join(chunks)

def make_chart(lat, stars, event, output):
    # Apparent solar time 21h: local hour angle of Sun = +9h.
    lst = sun_ra(solar_longitude(event)) + math.radians(135)
    title = ('+' if lat>0 else '') + str(lat) + '°'
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 900" role="img" aria-label="March equinox panorama at {title} latitude">', '<rect width="900" height="900" fill="#071527"/>',f'<text x="450" y="43" text-anchor="middle" fill="white" font-size="25">March equinox · {title} latitude</text>', '<text x="450" y="72" text-anchor="middle" fill="#b9d5e6" font-size="15">21:00 local apparent solar time · horizon-centered azimuthal equidistant projection</text>',f'<circle cx="450" cy="450" r="{RADIUS}" fill="none" stroke="#c1d0e4" stroke-width="2"/>']
    for altitude in (30,60):
        r=RADIUS*(90-altitude)/90
        s.append(f'<circle cx="450" cy="450" r="{r}" fill="none" stroke="#38516c" stroke-dasharray="3 6"/>')
    for label, x,y in [('N',450,78),('E',824,454),('S',450,828),('W',76,454)]:
        s.append(f'<text x="{x}" y="{y}" fill="#f2df9d" text-anchor="middle" font-size="21">{label}</text>')
    # Sample in equatorial coordinates; break curves at horizon and at large jumps.
    for dec, color, dash in [(0,'#65cbd6',''),(23.4393,'#c78cfa','5 5'),(-23.4393,'#c78cfa','5 5')]:
        pts=[]
        for i in range(721):
            p=project(math.radians(i/2),math.radians(dec),lat,lst)
            if p and pts and pts[-1] and math.dist(p,pts[-1])>30:pts.append(None)
            pts.append(p)
        s.append(svg_poly(pts,color,1.7,dash))
    eps=math.radians(23.4393)
    pts=[]
    for i in range(721):
        lam=math.radians(i/2)
        ra=math.atan2(math.cos(eps)*math.sin(lam),math.cos(lam))
        dec=math.asin(math.sin(eps)*math.sin(lam))
        p=project(ra,dec,lat,lst)
        if p and pts and pts[-1] and math.dist(p,pts[-1])>30:pts.append(None)
        pts.append(p)
    s.append(svg_poly(pts,'#efc36d',2))
    for star in stars:
        try:
            ra=math.radians(float(star['ra_h'])*15)
            dec=math.radians(float(star['dec_deg']))
            mag=float(star['representative_vmax'])
        except (ValueError,KeyError):continue
        p=project(ra,dec,lat,lst)
        if not p:continue
        x,y=p; radius=max(1.1,4.5-mag*.8)
        s.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="#e5eefc"/>')
        if mag<1.4 and star.get('proper'):
            name=star['proper'].replace('&','&amp;')
            s.append(f'<text x="{x+7:.1f}" y="{y-6:.1f}" fill="#c6dbed" font-size="12">{name}</text>')
    s.append('<text x="450" y="871" fill="#9bb8cc" text-anchor="middle" font-size="13">Gold: ecliptic · Cyan: celestial equator · Violet: celestial tropics · Star Almanack</text></svg>')
    output.write_text('\n'.join(s),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--year',type=int,default=2026)
    parser.add_argument('--output',type=Path,default=ROOT/'star-almanack/chart-library/panoramic')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    with (ROOT/'bright-stars-2mag.csv').open(newline='',encoding='utf-8') as f:
        stars=list(csv.DictReader(f))
    event=equinox(args.year)
    manifest={'year':args.year,'event':'March equinox','event_utc_approx':event.isoformat()+'Z','time':'21:00 local apparent solar time','projection':'azimuthal equidistant','catalog':'bright-stars-2mag.csv','views':[]}
    for lat in LATITUDES:
        name=f'march-equinox-{args.year}-lat-{lat:+d}.svg'
        make_chart(lat,stars,event,args.output/name)
        manifest['views'].append({'latitude':lat,'file':name})
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Generated',len(manifest['views']),'panoramas in',args.output)

if __name__=='__main__':main()
