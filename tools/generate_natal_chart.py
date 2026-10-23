#!/usr/bin/env python3
"""Calculate and render Nativitas natal charts from stored SPK kernels."""
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
# Explicit Astrodienst-style major-aspect orbs chosen for this chart.
ASPECTS = [('conjunction','☌',0,10), ('sextile','⚹',60,6),
           ('square','□',90,10), ('trine','△',120,10), ('opposition','☍',180,10)]


def major_aspects(rows):
    """Each unordered pair appears once; orb is departure from the exact angle."""
    results = []
    for i, first in enumerate(rows):
        for second in rows[i+1:]:
            difference = abs((first['longitude'] - second['longitude']) % 360)
            separation = min(difference, 360-difference)
            for name, symbol, angle, limit in ASPECTS:
                orb = abs(separation-angle)
                if orb <= limit + 1e-10:
                    results.append(dict(first=first, second=second, name=name,
                                        symbol=symbol, separation=separation, orb=orb))
                    break
    return results


def orb_position(orb):
    degree, minute = divmod(int(math.floor(orb*60+0.5)),60)
    return f'{degree}°{minute:02d}′'


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
        base = theta + math.radians(offset)
        low, high = base - fraction * math.pi / 2, base + fraction * math.pi / 2
        # The semi-arc correction is bounded by fraction*pi/2. Bisection
        # converges where fixed-point iteration can oscillate near the poles.
        for _ in range(80):
            ra = (low + high) / 2
            lam = ecliptic(ra)
            dec = math.asin(math.sin(eps) * math.sin(lam))
            ad = math.asin(math.tan(phi) * math.tan(dec))
            residual = ra - base - fraction * ad
            if abs(residual) < 1e-13:
                return math.degrees(ecliptic(ra)) % 360
            if residual < 0:
                low = ra
            else:
                high = ra
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


def render(rows, instant, zone, houses, latitude, longitude, *, fragment=False):
    def xy(angle, radius):
        return point(angle - (houses[0] if houses else 0), radius)

    # Preserve true longitudes without leader lines, even in a tight grouping.
    # Extra radial lanes enlarge the wheel only when the usual two do not fit.
    centers = []
    radii = (226, 140, *range(316, 1217, 90))
    used_radius = 226
    for row in rows:
        for radius in radii:
            x, y = xy(row['longitude'], radius)
            if all(abs(x-px) >= 70 or abs(y-py) >= 54 for px, py in centers):
                break
        else:
            raise ValueError('Symbols do not fit without overlap at their true angles')
        centers.append((x, y))
        used_radius = max(used_radius, radius)
    rim = used_radius + 44
    margin = rim + 82

    aspects = major_aspects(rows)
    house_description = 'Twelve Placidus houses; the Ascendant is at the left.' if houses else 'Birth time unknown: no houses or chart angles. Aries is at the left.'
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{320-margin} {320-margin} {2*margin} {2*margin}" role="img" aria-labelledby="chart-title chart-desc">',
           '<title id="chart-title">Planetary positions at the selected instant</title>',
           f'<desc id="chart-desc">Tropical zodiac and geocentric apparent planet positions. {house_description} Blue lines show trines and dashed sextiles; red lines show squares and oppositions. Conjunctions are listed in the aspect table.</desc>',
           f'<circle cx="320" cy="320" r="{rim+40}" fill="#101a2c" stroke="#f0c987"/>',
           f'<circle cx="320" cy="320" r="{rim}" fill="none" stroke="#64768c"/>']
    for degree in range(360):
        a = xy(degree,rim); b = xy(degree,rim+(10 if degree%10==0 else 6 if degree%5==0 else 3))
        svg.append(f'<path d="M{a[0]:.4f},{a[1]:.4f} L{b[0]:.4f},{b[1]:.4f}" stroke="#64768c" stroke-width="0.8"/>')
    for i,symbol in enumerate(SIGNS):
        a,b = xy(i*30,rim),xy(i*30,rim+40)
        x,y=xy(i*30+15,rim+20)
        svg.append(f'<path d="M{a[0]:.4f},{a[1]:.4f} L{b[0]:.4f},{b[1]:.4f}" stroke="#64768c"/>')
        svg.append(f'<text x="{x:.4f}" y="{y:.4f}" fill="#f0c987" font-size="27">{symbol}&#xfe0e;</text>')
    svg.append('<circle cx="320" cy="320" r="80" fill="none" stroke="#64768c"/>')
    for aspect in aspects:
        if aspect['name'] == 'conjunction':
            continue  # Nearly coincident points do not need an interior chord.
        a = xy(aspect['first']['longitude'],78)
        b = xy(aspect['second']['longitude'],78)
        color = '#75b9f4' if aspect['name'] in ('sextile','trine') else '#ef7e83'
        dash = ' stroke-dasharray="3 3"' if aspect['name'] == 'sextile' else ''
        title = f"{aspect['first']['body'].title()} {aspect['symbol']} {aspect['second']['body'].title()} · {aspect['name']} · orb {orb_position(aspect['orb'])}"
        svg.append(f'<line data-aspect="{aspect["name"]}" data-first="{aspect["first"]["body"]}" data-second="{aspect["second"]["body"]}" x1="{a[0]:.4f}" y1="{a[1]:.4f}" x2="{b[0]:.4f}" y2="{b[1]:.4f}" stroke="{color}" stroke-width="1.5"{dash}><title>{title}</title></line>')
    for i, cusp in enumerate(houses or []):
        a, b = xy(cusp,80), xy(cusp,rim)
        color = '#f0c987' if i in (0,3,6,9) else '#64768c'
        svg.append(f'<path data-house="{i+1}" data-longitude="{cusp:.10f}" d="M{a[0]:.4f},{a[1]:.4f} L{b[0]:.4f},{b[1]:.4f}" stroke="{color}" stroke-width="1"/>')
        middle = cusp + ((houses[(i+1)%12]-cusp)%360)/2
        x,y = xy(middle,101)
        svg.append(f'<text x="{x:.4f}" y="{y:.4f}" font-size="16" fill="#bdc9d6">{i+1}</text>')
    for i, name in (((0,'AS'),(3,'IC'),(6,'DS'),(9,'MC')) if houses else []):
        x,y = xy(houses[i],rim+60)
        svg.append(f'<text x="{x:.4f}" y="{y:.4f}" font-size="16" fill="#f0c987">{name}</text>')
    for row, (x, y) in zip(rows, centers):
        angle=row['longitude']
        a,b=xy(angle,rim),xy(angle,rim-6)
        svg.append(f'<path data-body="{row["body"]}" data-longitude="{angle:.10f}" d="M{a[0]:.4f},{a[1]:.4f} L{b[0]:.4f},{b[1]:.4f}" stroke="#f7f2e9" stroke-width="2"/>')
        svg.append(f'<g aria-label="{row["body"].title()} {sign_position(row["longitude"])}"><rect x="{x-35:.4f}" y="{y-27:.4f}" width="70" height="54" rx="4" fill="#101a2c"/><text x="{x:.4f}" y="{y-9:.4f}" font-size="32" fill="#f7f2e9">{row["symbol"]}&#xfe0e;</text><text x="{x:.4f}" y="{y+18:.4f}" font-size="15" fill="#f0c987">{sign_position(row["longitude"])}&#xfe0e;</text></g>')
    svg.append('</svg>')
    # Verify symbol blocks remain separate while retaining true longitudes.
    assert all(abs(x-px)>=70 or abs(y-py)>=54 for i,(x,y) in enumerate(centers) for px,py in centers[:i])
    local=instant.astimezone(ZoneInfo(zone))
    label=local.strftime('%B %d, %Y · %-I:%M %p %Z')
    wheel='\n'.join(svg)
    cusp_rows = ''.join(f'<tr><th scope="row">{i+1}</th><td>{sign_position(cusp)}&#xfe0e;</td></tr>' for i,cusp in enumerate(houses or []))
    position_rows = ''.join(f'<tr><th scope="row">{row["symbol"]}&#xfe0e; {row["body"].title()}</th><td>{sign_position(row["longitude"])}&#xfe0e;</td></tr>' for row in rows)
    aspect_rows = ''.join(f'<tr><td><span title="{a["first"]["body"].title()} and {a["second"]["body"].title()}">{a["first"]["symbol"]}&#xfe0e; {a["second"]["symbol"]}&#xfe0e;</span></td><td>{a["symbol"]} {a["name"].title()}</td><td>{orb_position(a["orb"])}</td></tr>' for a in aspects)
    page = '''---
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
<p class="tagline">Your selected sky</p>
<p class="chart-intro">LABEL<br><time datetime="STAMP">UTCSTAMP</time></p>
<figure class="wheel">WHEEL</figure>
<p class="chart-note">HOUSE_DESCRIPTION</p>
<details open><summary>Planet positions</summary><table><caption>Geocentric apparent positions in the tropical zodiac</caption><thead><tr><th>Body</th><th>Position</th></tr></thead><tbody>POSITIONS</tbody></table></details>
<p class="chart-note"><span style="color:#75b9f4">Blue: △ trine, dashed ⚹ sextile.</span> <span style="color:#ef7e83">Red: □ square, ☍ opposition.</span> Conjunctions ☌ are listed below without a line.</p>
<details><summary>Major aspects (ASPECTCOUNT)</summary><table><caption>Planet pairs and departure from an exact aspect</caption><thead><tr><th>Planets</th><th>Aspect</th><th>Orb</th></tr></thead><tbody>ASPECTROWS</tbody></table><p class="chart-note">Orbs: 10° for conjunctions, squares, trines and oppositions; 6° for sextiles. All eleven displayed bodies are included; aspects to house cusps and chart angles are omitted. Orb choices are astrological conventions.</p></details>
HOUSE_TABLE
<p class="chart-note">Geocentric apparent ecliptic longitudes of date, calculated with our stored DE440s and Ceres source kernels through Skyfield. Placidus houses, when shown, use the selected coordinates and local apparent sidereal time. Planet positions remain provisional pending independent validation.</p>
</main>
{% include nativitas-footer.html %}
</body>
</html>
'''.replace('LABEL',html.escape(label)).replace('UTCSTAMP',instant.strftime('%Y-%m-%d %H:%M UTC')).replace('STAMP',instant.isoformat()).replace('WHEEL',wheel).replace('POSITIONS',position_rows).replace('HOUSE_DESCRIPTION', 'Tropical zodiac with twelve Placidus houses. AS is the Ascendant, DS the Descendant, MC the Midheaven, and IC the lower meridian. The Ascendant sits at the left.' if houses else 'Birth time unknown. Positions and aspects are a noon snapshot in the selected timezone, not exact birth positions. The Moon can move substantially during the day. Houses and chart angles are omitted.').replace('HOUSE_TABLE', f'<details><summary>House cusp positions</summary><table><caption>Placidus · {latitude:.4f}°, {longitude:.4f}°</caption><thead><tr><th>House</th><th>Position</th></tr></thead><tbody>{cusp_rows}</tbody></table></details>' if houses else '').replace('ASPECTROWS',aspect_rows).replace('ASPECTCOUNT',str(len(aspects)))
    return page.split('<main class="page-shell">', 1)[1].split('</main>', 1)[0].replace('<h1>Natal Chart</h1>', '') if fragment else page


def calculate_natal(instant, latitude, longitude, zone, *, unknown_time=False, engine=None):
    if instant.tzinfo is None:
        raise ValueError('Explicit UTC offset required')
    if not all(math.isfinite(v) for v in (latitude, longitude)) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError('Valid latitude and longitude required')
    instant = instant.astimezone(timezone.utc)
    if not 1900 <= instant.year <= 2099:
        raise ValueError('Choose an instant from 1900 through 2099')
    ZoneInfo(zone)  # Validate before calculation.
    if unknown_time and instant.astimezone(ZoneInfo(zone)).strftime('%H:%M:%S') != '12:00:00':
        raise ValueError('An unknown birth time requires a noon snapshot in the selected timezone')
    engine = engine or StarAlmanackEphemeris()
    t = engine.ts.from_datetime(instant)
    houses = None if unknown_time else placidus_houses(t, latitude, longitude)
    earth = engine.earth.at(t)
    rows = []
    for body, symbol in BODIES:
        _, lon, _ = earth.observe(engine._body(body)).apparent().frame_latlon(ecliptic_frame)
        rows.append(dict(body=body, symbol=symbol, longitude=float(lon.degrees) % 360))
        print('COMPUTED', body, flush=True)
    return dict(instant_utc=instant.isoformat(), timezone=zone,
                observer=dict(latitude=latitude, longitude=longitude),
                unknown_time=unknown_time, houses=houses, bodies=rows,
                aspects=major_aspects(rows),
                chart_html=render(rows, instant, zone, houses, latitude, longitude, fragment=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instant',required=True,help='ISO 8601 with explicit UTC offset')
    parser.add_argument('--timezone',default='America/Los_Angeles')
    parser.add_argument('--kernel-dir',type=Path)
    parser.add_argument('--latitude',type=float,default=34.1083)
    parser.add_argument('--longitude',type=float,default=-117.2898)
    parser.add_argument('--unknown-time',action='store_true',help='Omit houses; instant must be local noon')
    parser.add_argument('--output',type=Path,default=Path('nativitas/natal-sample.html'))
    args=parser.parse_args()
    instant=datetime.fromisoformat(args.instant.replace('Z','+00:00'))
    if instant.tzinfo is None: parser.error('Explicit UTC offset required')
    instant=instant.astimezone(timezone.utc)
    engine=StarAlmanackEphemeris(args.kernel_dir)
    report=calculate_natal(instant,args.latitude,args.longitude,args.timezone,
                          unknown_time=args.unknown_time,engine=engine)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(render(report['bodies'],instant,args.timezone,report['houses'],args.latitude,args.longitude))
    print('Saved',args.output,'with',len(report['bodies']),'calculated body positions')

if __name__=='__main__':main()
