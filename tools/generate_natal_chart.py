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


def render(rows, instant, zone):
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" role="img" aria-labelledby="chart-title chart-desc">',
           '<title id="chart-title">Tonight’s planetary positions</title>',
           '<desc id="chart-desc">Tropical zodiac with geocentric apparent planet positions. Planet symbols remain at their calculated angles, with degree and minute positions and no leader lines. Houses and aspects are not included in this first stage.</desc>',
           '<circle cx="320" cy="320" r="310" fill="#101a2c" stroke="#f0c987"/>',
           '<circle cx="320" cy="320" r="270" fill="none" stroke="#64768c"/>']
    for degree in range(360):
        a = point(degree,270); b = point(degree,270+(10 if degree%10==0 else 6 if degree%5==0 else 3))
        svg.append(f'<path d="M{a[0]:.4f},{a[1]:.4f} L{b[0]:.4f},{b[1]:.4f}" stroke="#64768c" stroke-width="0.8"/>')
    for i,symbol in enumerate(SIGNS):
        a,b = point(i*30,270),point(i*30,310)
        x,y=point(i*30+15,290)
        svg.append(f'<path d="M{a[0]:.4f},{a[1]:.4f} L{b[0]:.4f},{b[1]:.4f}" stroke="#64768c"/>')
        svg.append(f'<text x="{x:.4f}" y="{y:.4f}" fill="#f0c987" font-size="27">{symbol}&#xfe0e;</text>')
    centers=[]
    for row in rows:
        angle=row['longitude']
        for radius in (226,140,54):
            x,y=point(angle,radius)
            if all(abs(x-px)>=70 or abs(y-py)>=44 for px,py in centers): break
        else: raise ValueError('Symbols do not fit without overlap at their true angles')
        centers.append((x,y))
        a,b=point(angle,270),point(angle,264)
        svg.append(f'<path data-body="{row["body"]}" data-longitude="{angle:.10f}" d="M{a[0]:.4f},{a[1]:.4f} L{b[0]:.4f},{b[1]:.4f}" stroke="#f7f2e9" stroke-width="2"/>')
        svg.append(f'<g aria-label="{row["body"].title()} {sign_position(row["longitude"])}"><text x="{x:.4f}" y="{y-9:.4f}" font-size="32" fill="#f7f2e9">{row["symbol"]}&#xfe0e;</text><text x="{x:.4f}" y="{y+18:.4f}" font-size="15" fill="#f0c987">{sign_position(row["longitude"])}&#xfe0e;</text></g>')
    svg.append('</svg>')
    # Verify symbol blocks remain separate while retaining true longitudes.
    assert all(abs(x-px)>=70 or abs(y-py)>=44 for i,(x,y) in enumerate(centers) for px,py in centers[:i])
    local=instant.astimezone(ZoneInfo(zone))
    label=local.strftime('%B %d, %Y · %-I:%M %p %Z')
    wheel='\n'.join(svg)
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
</style>
</head>
<body>
{% include nativitas-nav.html %}
<main class="page-shell">
<h1>Natal Chart</h1>
<p class="tagline">Tonight’s sky · San Bernardino</p>
<p class="chart-intro">LABEL<br><time datetime="STAMP">UTCSTAMP</time></p>
<figure class="wheel">WHEEL</figure>
<p class="chart-note">First stage: planet symbols and their degrees and minutes in the tropical zodiac. Symbols remain at their calculated angles. Nearby symbols use different distances from the center; small rim ticks mark the exact longitudes. There are no leader lines. Houses and aspect lines will follow.</p>
<p class="chart-note">Geocentric apparent ecliptic longitudes of date, calculated with our stored DE440s and Ceres source kernels through Skyfield. San Bernardino sets the displayed local time; these planet positions are measured from Earth’s center. Values are provisional pending independent validation.</p>
</main>
{% include nativitas-footer.html %}
</body>
</html>
'''.replace('LABEL',html.escape(label)).replace('UTCSTAMP',instant.strftime('%Y-%m-%d %H:%M UTC')).replace('STAMP',instant.isoformat()).replace('WHEEL',wheel)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instant',required=True,help='ISO 8601 with explicit UTC offset')
    parser.add_argument('--timezone',default='America/Los_Angeles')
    parser.add_argument('--kernel-dir',type=Path)
    parser.add_argument('--output',type=Path,default=Path('nativitas/natal-chart.html'))
    args=parser.parse_args()
    instant=datetime.fromisoformat(args.instant.replace('Z','+00:00'))
    if instant.tzinfo is None: parser.error('Explicit UTC offset required')
    instant=instant.astimezone(timezone.utc)
    engine=StarAlmanackEphemeris(args.kernel_dir)
    earth=engine.earth.at(engine.ts.from_datetime(instant))
    rows=[]
    for body,symbol in BODIES:
        _,lon,_=earth.observe(engine._body(body)).apparent().frame_latlon(ecliptic_frame)
        rows.append({'body':body,'symbol':symbol,'longitude':float(lon.degrees)%360})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(render(rows,instant,args.timezone))
    print('Saved',args.output,'with',len(rows),'calculated body positions')

if __name__=='__main__':main()
