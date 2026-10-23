#!/usr/bin/env python3
"""Generate the first Nativitas zodiac/planet chart from stored SPK kernels."""
import argparse
import html
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from star_almanack_ephemeris import StarAlmanackEphemeris
from skyfield.framelib import ecliptic_frame

BODIES = [('sun','☉'),('moon','☽'),('mercury','☿'),('venus','♀'),('mars','♂'),
          ('ceres','⚳'),('jupiter','♃'),('saturn','♄'),('uranus','♅'),('neptune','♆'),('pluto','♇')]
SIGNS = '♈♉♊♋♌♍♎♏♐♑♒♓'


def point(angle, radius):
    a = math.radians(angle)
    return 320-radius*math.cos(a), 320+radius*math.sin(a)


def sign_position(longitude):
    minutes = int(math.floor(longitude*60+0.5)) % 21600
    sign, minutes = divmod(minutes, 1800)
    degree, minute = divmod(minutes, 60)
    return f'{degree}°{minute:02d}′ {SIGNS[sign]}'


def placidus_houses(t, latitude, longitude):
    """Solve the Placidus semi-arc equations, using true obliquity and GAST.

    Intermediate cusps trisect semi-diurnal and semi-nocturnal arcs.
    Polar latitudes are rejected explicitly; no other house system is substituted.
    """
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError('Finite geographic coordinates required; longitude must be -180 to 180')
    eps = float(t._mean_obliquity_radians + t._nutation_angles_radians[1])
    phi = math.radians(latitude)
    if abs(phi) >= math.pi / 2 - eps:
        raise ValueError('Placidus is not supported at or beyond the polar circles')
    theta = math.radians((float(t.gast) * 15 + longitude) % 360)

    def ecliptic(ra):
        return math.atan2(math.sin(ra), math.cos(eps) * math.cos(ra))

    def cusp(offset, fraction):
        ra = theta + math.radians(offset)
        for _ in range(200):
            lam = ecliptic(ra)
            dec = math.asin(math.sin(eps) * math.sin(lam))
            ad = math.asin(math.tan(phi) * math.tan(dec))
            following = theta + math.radians(offset) + fraction * ad
            if abs(following - ra) < 1e-13:
                return math.degrees(ecliptic(following)) % 360
            ra = following
        raise ValueError('Placidus cusp did not converge')

    houses = [0.0] * 12
    houses[0] = cusp(90, 1)
    houses[1], houses[2] = cusp(120, 2/3), cusp(150, 1/3)
    houses[9] = math.degrees(ecliptic(theta)) % 360
    houses[10], houses[11] = cusp(30, 1/3), cusp(60, 2/3)
    for index in (0, 1, 2, 9, 10, 11):
        houses[(index + 6) % 12] = (houses[index] + 180) % 360
    widths = [(houses[(i+1)%12] - houses[i]) % 360 for i in range(12)]
    if abs(sum(widths) - 360) > 1e-8 or min(widths) <= 0:
        raise ValueError('Invalid Placidus cusp order')
    return houses


def render(rows, instant, zone, houses, latitude, longitude):
    def xy(angle, radius):
        return point(angle - houses[0], radius)

    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="-32 -32 704 704" role="img" aria-labelledby="chart-title chart-desc">',
           '<title id="chart-title">Tonight’s planetary positions</title>',
           '<desc id="chart-desc">Tropical zodiac, geocentric apparent planet positions, and twelve Placidus houses. The Ascendant is at the left. AS, DS, MC and IC mark the four angles. Aspect lines are not yet included.</desc>',
           '<circle cx="320" cy="320" r="310" fill="#101a2c" stroke="#f0c987"/>',
           '<circle cx="320" cy="320" r="270" fill="none" stroke="#64768c"/>']
    for degree in range(360):
        a = xy(degree,270); b = xy(degree,270+(10 if degree%10==0 else 6 if degree%5==0 else 3))
        svg.append(f'<path d="M{a[0]:.4f},{a[1]:.4f} L{b[0]:.4f},{b[1]:.4f}" stroke="#64768c" stroke-width="0.8"/>')
    for i,symbol in enumerate(SIGNS):
        a,b = xy(i*30,270),xy(i*30,310)
        x,y=xy(i*30+15,290)
        svg.append(f'<path d="M{a[0]:.4f},{a[1]:.4f} L{b[0]:.4f},{b[1]:.4f}" stroke="#64768c"/>')
        svg.append(f'<text x="{x:.4f}" y="{y:.4f}" fill="#f0c987" font-size="27">{symbol}&#xfe0e;</text>')
    svg.append('<circle cx="320" cy="320" r="80" fill="none" stroke="#64768c"/>')
    for i, cusp in enumerate(houses):
        a, b = xy(cusp,80), xy(cusp,270)
        color = '#f0c987' if i in (0,3,6,9) else '#64768c'
        svg.append(f'<path data-house="{i+1}" data-longitude="{cusp:.10f}" d="M{a[0]:.4f},{a[1]:.4f} L{b[0]:.4f},{b[1]:.4f}" stroke="{color}" stroke-width="1"/>')
        middle = cusp + ((houses[(i+1)%12]-cusp)%360)/2
        x,y = xy(middle,101)
        svg.append(f'<text x="{x:.4f}" y="{y:.4f}" font-size="16" fill="#bdc9d6">{i+1}</text>')
    for i, name in ((0,'AS'),(3,'IC'),(6,'DS'),(9,'MC')):
        x,y = xy(houses[i],330)
        svg.append(f'<text x="{x:.4f}" y="{y:.4f}" font-size="16" fill="#f0c987">{name}</text>')
    centers=[]
    for row in rows:
        angle=row['longitude']
        for radius in (226,140,54):
            x,y=xy(angle,radius)
            if all(abs(x-px)>=70 or abs(y-py)>=54 for px,py in centers): break
        else: raise ValueError('Symbols do not fit without overlap at their true angles')
        centers.append((x,y))
        a,b=xy(angle,270),xy(angle,264)
        svg.append(f'<path data-body="{row["body"]}" data-longitude="{angle:.10f}" d="M{a[0]:.4f},{a[1]:.4f} L{b[0]:.4f},{b[1]:.4f}" stroke="#f7f2e9" stroke-width="2"/>')
        svg.append(f'<g aria-label="{row["body"].title()} {sign_position(row["longitude"])}"><rect x="{x-35:.4f}" y="{y-27:.4f}" width="70" height="54" rx="4" fill="#101a2c"/><text x="{x:.4f}" y="{y-9:.4f}" font-size="32" fill="#f7f2e9">{row["symbol"]}&#xfe0e;</text><text x="{x:.4f}" y="{y+18:.4f}" font-size="15" fill="#f0c987">{sign_position(row["longitude"])}&#xfe0e;</text></g>')
    svg.append('</svg>')
    # Verify symbol blocks remain separate while retaining true longitudes.
    assert all(abs(x-px)>=70 or abs(y-py)>=54 for i,(x,y) in enumerate(centers) for px,py in centers[:i])
    local=instant.astimezone(ZoneInfo(zone))
    label=local.strftime('%B %d, %Y · %-I:%M %p %Z')
    wheel='\n'.join(svg)
    cusp_rows = ''.join(f'<tr><th scope="row">{i+1}</th><td>{sign_position(cusp)}</td></tr>' for i,cusp in enumerate(houses))
    return '''---
layout: null
---
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Natal Chart | Nativitas</title>
<link rel="stylesheet" href="nativitas.css">
<style>
.chart-intro,.chart-note{max-width:44rem;color:var(--muted)}
.wheel{max-width:46rem;margin:2rem auto}
.wheel svg{display:block;width:100%;height:auto;font-family:"DejaVu Sans","Segoe UI Symbol","Apple Symbols",sans-serif;text-anchor:middle;dominant-baseline:central}
table{border-collapse:collapse;max-width:28rem;width:100%}th,td{border:1px solid #64768c;padding:.35rem .75rem;text-align:left}
</style>
</head>
<body>
{% include nativitas-nav.html %}
<main class="page-shell">
<h1>Natal Chart</h1>
<p class="tagline">Tonight’s sky · San Bernardino</p>
<p class="chart-intro">LABEL<br><time datetime="STAMP">UTCSTAMP</time></p>
<figure class="wheel">WHEEL</figure>
<p class="chart-note">Tropical zodiac with twelve Placidus houses. AS is the Ascendant, DS the Descendant, MC the Midheaven, and IC the lower meridian. The Ascendant sits at the left. Aspect lines are next.</p>
<details><summary>House cusp positions</summary><table><caption>Placidus · COORDINATES</caption><thead><tr><th>House</th><th>Position</th></tr></thead><tbody>CUSPS</tbody></table></details>
<p class="chart-note">Geocentric apparent ecliptic longitudes of date, calculated with our stored DE440s and Ceres source kernels through Skyfield. Houses use San Bernardino’s coordinates and local apparent sidereal time. Planet positions remain provisional pending independent validation.</p>
</main>
{% include nativitas-footer.html %}
</body>
</html>
'''.replace('LABEL',html.escape(label)).replace('UTCSTAMP',instant.strftime('%Y-%m-%d %H:%M UTC')).replace('STAMP',instant.isoformat()).replace('WHEEL',wheel).replace('CUSPS',cusp_rows).replace('COORDINATES',f'{latitude:.4f}°, {longitude:.4f}°')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instant',required=True,help='ISO 8601 with explicit UTC offset')
    parser.add_argument('--timezone',default='America/Los_Angeles')
    parser.add_argument('--kernel-dir',type=Path)
    parser.add_argument('--latitude',type=float,default=34.1083)
    parser.add_argument('--longitude',type=float,default=-117.2898)
    parser.add_argument('--output',type=Path,default=Path('nativitas/natal-chart.html'))
    args=parser.parse_args()
    instant=datetime.fromisoformat(args.instant.replace('Z','+00:00'))
    if instant.tzinfo is None: parser.error('Explicit UTC offset required')
    instant=instant.astimezone(timezone.utc)
    engine=StarAlmanackEphemeris(args.kernel_dir)
    t=engine.ts.from_datetime(instant)
    houses=placidus_houses(t,args.latitude,args.longitude)
    earth=engine.earth.at(t)
    rows=[]
    for body,symbol in BODIES:
        _,lon,_=earth.observe(engine._body(body)).apparent().frame_latlon(ecliptic_frame)
        rows.append({'body':body,'symbol':symbol,'longitude':float(lon.degrees)%360})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(render(rows,instant,args.timezone,houses,args.latitude,args.longitude))
    print('Saved',args.output,'with',len(rows),'calculated body positions')

if __name__=='__main__':main()
