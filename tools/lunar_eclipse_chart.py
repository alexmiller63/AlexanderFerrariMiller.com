"""Original detailed lunar eclipse charts from local geometric ephemerides.

No reference diagrams, predictions, coastlines, or network services are used.
"""
import csv
from datetime import datetime, timedelta
from functools import lru_cache
import html
import io
import json
import math
from pathlib import Path
import sys

import numpy as np
from skyfield.framelib import ecliptic_J2000_frame, itrs
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eclipse_engine import MOON_RADIUS_KM, EARTH_RADIUS_KM, gregorian_to_jd, utc_to_tdb_approx
from kernel_eclipse_engine import KernelEclipseEngine
from lunar_eclipse_engine import lunar_shadow_at_utc_jd

ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT / 'star-almanack/assets/ephemera/de440s.bsp'
LABELS = {'P1': 'Penumbral ingress', 'U1': 'Umbral ingress', 'U2': 'Totality begins',
          'MAX': 'Greatest eclipse', 'U3': 'Totality ends', 'U4': 'Umbral egress', 'P4': 'Penumbral egress'}


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def iso(value):
    return value.isoformat(timespec='seconds').replace('+00:00', 'Z')


def julian(value):
    return gregorian_to_jd(value.year, value.month, value.day,
                           value.hour + value.minute/60 + (value.second+value.microsecond/1e6)/3600)


@lru_cache(maxsize=1)
def engine():
    return KernelEclipseEngine(KERNEL)


def sample(value):
    eng = engine()
    jd = julian(value)
    t = eng.timescale.tdb_jd(utc_to_tdb_approx(jd))
    # Use the same time convention and instantaneous positions as the catalog.
    rotation = ecliptic_J2000_frame.rotation_at(t).T
    mv = eng.moon_vector_j2000(float(t.tdb))
    sv = eng.sun_vector_j2000(float(t.tdb))
    moon = rotation @ np.array([mv.x, mv.y, mv.z])
    sun = rotation @ np.array([sv.x, sv.y, sv.z])
    axis = -sun / np.linalg.norm(sun)
    east = np.cross([0., 0., 1.], axis)
    east /= np.linalg.norm(east)
    north = np.cross(axis, east)
    shadow = lunar_shadow_at_utc_jd(eng, jd)
    terrestrial = itrs.rotation_at(t) @ moon
    return dict(utc=iso(value), x_km=float(-moon @ east), y_km=float(moon @ north),
                moon_distance_km=float(np.linalg.norm(moon)),
                umbra_radius_km=shadow.umbra_radius_km,
                penumbra_radius_km=shadow.penumbra_radius_km,
                earth_fixed_moon_km=terrestrial.tolist(),
                sun_ra_deg=math.degrees(math.atan2(sun[1],sun[0]))%360,
                sun_dec_deg=math.degrees(math.asin(sun[2]/np.linalg.norm(sun))),
                moon_ra_deg=math.degrees(math.atan2(moon[1],moon[0]))%360,
                moon_dec_deg=math.degrees(math.asin(moon[2]/np.linalg.norm(moon))))


@lru_cache(maxsize=32)
def _calculate(key):
    event = json.loads(key)
    contacts = event['contacts_utc']
    if isinstance(contacts, str):
        contacts = json.loads(contacts)
    times = {**contacts, 'MAX':event['greatest_utc']}
    phases = [{**sample(instant(value)), 'phase':phase}
              for phase,value in sorted(times.items(),key=lambda kv:kv[1]) if value]
    if not contacts.get('P1') or not contacts.get('P4'):
        raise ValueError('Lunar chart requires P1 and P4')
    begin,end = instant(contacts['P1']),instant(contacts['P4'])
    track_begin,track_end=begin-timedelta(minutes=25),end+timedelta(minutes=25)
    count=math.ceil((track_end-track_begin).total_seconds()/120)
    track=[sample(track_begin+(track_end-track_begin)*i/count) for i in range(count+1)]
    maximum=next(p for p in phases if p['phase']=='MAX')
    if abs(math.hypot(maximum['x_km'],maximum['y_km'])-event['axis_distance_km']) > .02:
        raise ValueError('Chart and stored catalog geometry disagree; regenerate the catalog')
    return dict(schema_version=1, event_id=event['id'], phases=phases, track=track,
                moon_radius_km=MOON_RADIUS_KM,
                coordinates='Shadow-centered tangent plane; celestial north up, west right; kilometres',
                model='Instantaneous geocentric positions; spherical enlarged Earth shadow; same engine as catalog',
                position_source='Local JPL DE440s kernel; Star Almanack geometry',
                visibility_model='Spherical Earth, geometric topocentric Moon-center altitude; no refraction, terrain or twilight')


def calculate(event):
    return _calculate(json.dumps({k:event[k] for k in
        ('id','greatest_utc','contacts_utc','axis_distance_km')},sort_keys=True))


def above_horizon(moon,lat,lon):
    """Moon center above the geometric topocentric horizon of a spherical Earth."""
    phi,lam=np.radians(lat),np.radians(lon)
    normal=np.array([np.cos(phi)*np.cos(lam),np.cos(phi)*np.sin(lam),np.sin(phi)])
    return np.einsum('i,i...->...',np.asarray(moon),normal) > EARTH_RADIUS_KM


def downloads(event):
    data=calculate(event)
    buffer=io.StringIO(newline='')
    fields=['phase','utc','x_km','y_km','moon_distance_km','umbra_radius_km','penumbra_radius_km']
    writer=csv.DictWriter(buffer,fieldnames=fields,lineterminator='\n',extrasaction='ignore')
    writer.writeheader()
    writer.writerows(data['phases'])
    return {event['id']+'-chart.json':json.dumps(data,indent=2)+'\n',
            event['id']+'-contacts.csv':buffer.getvalue()}


def chart(event):
    data=calculate(event)
    phases,track=data['phases'],data['track']
    maximum=next(p for p in phases if p['phase']=='MAX')
    out=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 1880" role="img" aria-labelledby="chart-title chart-desc">',
         '<title id="chart-title">'+html.escape(event['date_utc']+' '+event['type']+' lunar eclipse — calculated event chart')+'</title>',
         '<desc id="chart-desc">Moon track through Earth’s shadow, celestial orientation, contact table, durations, geometry, and three geographic horizon maps. All calculated by Star Almanack.</desc>',
         '<defs><marker id="motion" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#ab562d"/></marker></defs>',
         '<rect width="1400" height="1880" fill="#fbf8ef"/>',
         '<style>text{font-family:DejaVu Sans,sans-serif;fill:#203747} .mono{font-family:DejaVu Sans Mono,monospace;font-variant-numeric:tabular-nums} .small{font-size:17px} .rule{stroke:#b8b3a4;stroke-width:1} .section{font-size:19px;letter-spacing:2px;font-weight:bold}</style>']
    def text(x,y,value,size=20,extra=''):
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" {extra}>{html.escape(str(value))}</text>')
    def line(x1,y1,x2,y2,extra='class="rule"'):
        out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" {extra}/>')
    text(50,45,'STAR ALMANACK  /  ECLIPSE STUDIES',17,'letter-spacing="3"')
    text(50,96,f'{event["type"].upper()} LUNAR ECLIPSE',40,'font-weight="bold"')
    text(50,135,instant(event['greatest_utc']).strftime('%d %B %Y')+'  ·  all clocks UTC',24)
    text(1350,45,event['id'],16,'text-anchor="end" class="mono"')
    line(50,158,1350,158)
    text(50,190,'01  /  THE MOON THROUGH EARTH’S SHADOW',19,'class="section"')
    # Fit the full calculated track and lunar limbs, with room for annotations.
    extent=max(max(abs(p['x_km']),abs(p['y_km']))+MOON_RADIUS_KM for p in track)
    extent=max(extent,maximum['penumbra_radius_km'])
    scale=350/extent
    cx,cy=470,640
    def xy(p): return cx+p['x_km']*scale,cy-p['y_km']*scale
    for name,key,fill in [('Penumbra','penumbra_radius_km','#e2ded0'),('Umbra','umbra_radius_km','#6c667b')]:
        radius=maximum[key]*scale
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{fill}" stroke="#606676"/>')
        text(cx,cy+radius-23,name.upper(),17,'text-anchor="middle" letter-spacing="2"')
    line(cx-17,cy,cx+17,cy)
    line(cx,cy-17,cx,cy+17)
    # Numbered coordinates measure physical displacement from the shadow axis.
    # Draw over the shadow fills so the grid remains visible inside both circles.
    step = 2000 if extent <= 16000 else 5000
    limit = math.floor(extent / step) * step
    out.append('<g id="shadow-coordinate-grid">')
    for value in range(-limit, limit+1, step):
        x, y = cx+value*scale, cy-value*scale
        line(x,cy-350,x,cy+350,'stroke="#526c7b" stroke-opacity=".28" stroke-dasharray="3 5"')
        line(cx-350,y,cx+350,y,'stroke="#526c7b" stroke-opacity=".28" stroke-dasharray="3 5"')
        if value % (2*step) == 0:
            text(x,1014,f'{value:+,}' if value else '0',14,'text-anchor="middle" class="mono"')
        text(112,y+5,f'{value:+,}' if value else '0',14,'text-anchor="end" class="mono"')
    out.append('</g>')
    text(470,1055,'Shadow-axis offsets (km): west +x, north +y',16,'text-anchor="middle"')
    points=' '.join(f'{xy(p)[0]:.2f},{xy(p)[1]:.2f}' for p in track)
    out.append(f'<polyline points="{points}" fill="none" stroke="#ab562d" stroke-width="2.5" marker-end="url(#motion)"/>')
    for i,p in enumerate(phases):
        x,y=xy(p)
        radius=MOON_RADIUS_KM*scale
        ismax=p['phase']=='MAX'
        out.append(f'<circle data-phase="{p["phase"]}" cx="{x}" cy="{y}" r="{radius}" fill="{"#e3ac61" if ismax else "#fffdf7"}" fill-opacity="{.95 if ismax else .28}" stroke="{"#9a4d21" if ismax else "#304f65"}" stroke-width="{2.7 if ismax else 1.5}"/>')
        # External labels alternate sides; short codes refer to the full table.
        sign=1 if i%2==0 else -1
        lx=x+sign*(radius+22)
        ly=y-62 if sign<0 else y+65
        line(x,y,lx,ly,'stroke="#526c7b" stroke-width="1"')
        text(lx,ly-7,p['phase'],19,'text-anchor="middle" font-weight="bold"')
        text(lx,ly+14,instant(p['utc']).strftime('%H:%M:%S'),16,'text-anchor="middle" class="mono"')
    text(470,232,'North',18,'text-anchor="middle"')
    line(470,273,470,244,'stroke="#203747" marker-end="url(#motion)"')
    text(70,282,'East',18)
    text(818,282,'West',18)
    text(470,1036,'South',16,'text-anchor="middle"')
    # Scale and orientation notes belong to the actual geometric view.
    length=5000*scale
    line(120,260,120+length,260,'stroke="#203747" stroke-width="3"')
    line(120,254,120,266,'stroke="#203747"')
    line(120+length,254,120+length,266,'stroke="#203747"')
    text(120,246,'5,000 km',16)
    text(50,1072,'Disk size and track are to scale. Shadow circles show their radii at greatest eclipse.',17)
    text(50,1098,'North is celestial north; east is left. Arrow follows increasing UTC. Gold marks greatest eclipse.',17)
    text(50,1124,'Outlined disks are contact positions, not surface photographs or predicted lunar brightness.',17)
    # Right-hand scientific ledger.
    text(930,230,'02  /  CONTACTS',19,'class="section"')
    text(930,261,'Phase       UTC clock',18,'class="mono"')
    for i,p in enumerate(phases):
        y=300+i*56
        text(930,y,p['phase'],21,'font-weight="bold"')
        text(1040,y,instant(p['utc']).strftime('%H:%M:%S'),21,'class="mono"')
        text(930,y+22,LABELS[p['phase']],16)
    dates={p['utc'][:10] for p in phases}
    text(930,715,'Contact date: '+next(iter(dates)) if len(dates)==1 else 'Dates span midnight; see records.',16)
    text(930,752,'03  /  DURATIONS',19,'class="section"')
    byphase={p['phase']:p for p in phases}
    for i,(a,b,label) in enumerate([('P1','P4','Penumbral event'),('U1','U4','Umbral event'),('U2','U3','Totality')]):
        y=786+i*49
        text(930,y,label,17)
        if a in byphase and b in byphase:
            sec=round((instant(byphase[b]['utc'])-instant(byphase[a]['utc'])).total_seconds())
            value=f'{sec//3600:02d}h {sec%3600//60:02d}m {sec%60:02d}s'
        else: value='Does not occur'
        text(930,y+23,value,19,'class="mono"')
    text(930,958,'04  /  GEOMETRY AT MAX',18,'class="section"')
    geom=[('Axis offset',f'{event["axis_distance_km"]:,.1f} km'),
          ('Umbral magnitude',f'{(maximum["umbra_radius_km"]+MOON_RADIUS_KM-event["axis_distance_km"])/(2*MOON_RADIUS_KM):.4f}'),
          ('Penumbral magnitude',f'{(maximum["penumbra_radius_km"]+MOON_RADIUS_KM-event["axis_distance_km"])/(2*MOON_RADIUS_KM):.4f}'),
          ('Moon distance',f'{maximum["moon_distance_km"]:,.0f} km'),
          ('Umbra radius',f'{maximum["umbra_radius_km"]:,.1f} km'),
          ('Penumbra radius',f'{maximum["penumbra_radius_km"]:,.1f} km'),
          ('Moon RA / Dec',f'{maximum["moon_ra_deg"]:.3f}° / {maximum["moon_dec_deg"]:+.3f}°'),
          ('Sun RA / Dec',f'{maximum["sun_ra_deg"]:.3f}° / {maximum["sun_dec_deg"]:+.3f}°')]
    for i,(label,val) in enumerate(geom):
        text(930,988+i*26,label,16)
        text(1350,988+i*26,val,16,'text-anchor="end" class="mono"')
    line(50,1190,1350,1190)
    text(50,1225,'05  /  VISIBILITY ON EARTH AT THREE INSTANTS',19,'class="section"')
    text(50,1253,'Blue: Moon center above the geometric horizon. Pale: below. Crosses identify selected places.',17)
    # Three independent geographical snapshots. No copied basemap/coastline data.
    cities=[('LA',34.05,-118.24),('NY',40.71,-74.01),('London',51.51,-.13),
            ('Cairo',30.04,31.24),('Tokyo',35.68,139.69),('Sydney',-33.87,151.21),
            ('Santiago',-33.45,-70.67),('Cape Town',-33.92,18.42)]
    lons=np.arange(-179.5,180,1.)
    lats=np.arange(-89.5,90,1.)
    lon_grid,lat_grid=np.meshgrid(lons,lats)
    for n,phase in enumerate(('P1','MAX','P4')):
        p=byphase[phase]
        mx,my,mw,mh=70+n*445,1330,390,195
        text(mx,my-40,phase+'  ·  '+instant(p['utc']).strftime('%H:%M:%S UTC'),20,'font-weight="bold"')
        text(mx,my-16,LABELS[phase],17)
        mask=above_horizon(p['earth_fixed_moon_km'],lat_grid,lon_grid)
        out.append(f'<rect x="{mx}" y="{my}" width="{mw}" height="{mh}" fill="#e7e4dc"/>')
        # Merge visible cells in each latitude row, retaining actual sampled edges.
        for j,row in enumerate(mask[::-1]):
            starts=np.where(np.diff(np.r_[False,row,False].astype(int))==1)[0]
            ends=np.where(np.diff(np.r_[False,row,False].astype(int))==-1)[0]
            for start,end in zip(starts,ends):
                out.append(f'<rect x="{mx+start*mw/360:.3f}" y="{my+j*mh/180:.3f}" width="{(end-start)*mw/360:.3f}" height="{mh/180+.02:.3f}" fill="#91b8ca"/>')
        def geo(lat,lon): return mx+(lon+180)/360*mw,my+(90-lat)/180*mh
        for lon in range(-180,181,60):
            x,_=geo(0,lon)
            line(x,my,x,my+mh,'stroke="#7e929a" stroke-width=".6"')
            text(x,my+mh+19,str(lon)+'°',13,'text-anchor="middle"')
        for lat in range(-60,61,30):
            _,y=geo(lat,0)
            line(mx,y,mx+mw,y,'stroke="#7e929a" stroke-width=".6"')
            text(mx-5,y+4,str(lat)+'°',12,'text-anchor="end"')
        for label,lat,lon in cities:
            x,y=geo(lat,lon)
            line(x-2,y,x+2,y,'stroke="#203747"')
            line(x,y-2,x,y+2,'stroke="#203747"')
            text(x+3,y+(13 if label in ('NY','Tokyo') else -4),label,11)
        out.append(f'<rect x="{mx}" y="{my}" width="{mw}" height="{mh}" fill="none" stroke="#536d7a"/>')
    text(50,1584,'Longitude increases eastward; latitude is geocentric. Maps use a 1° grid; boundaries are approximate.',17)
    text(50,1611,'These are horizon snapshots, not a claim that the entire event is visible in every blue region.',17)
    text(50,1638,'No atmospheric refraction, local terrain, clouds, or daylight suppression is included.',17)
    line(50,1660,1350,1660)
    text(50,1690,'06  /  CALCULATION NOTES',19,'class="section"')
    notes=[
        'Track sampled every ≤2 minutes, with contact positions evaluated at the catalog’s UTC instants.',
        'Shadow radii vary during the event; the two reference circles use the greatest-eclipse plane.',
        f'Effective Earth-radius factor: {event.get("shadow_earth_radius_factor",1.01):.3f}. Moon radius: {MOON_RADIUS_KM:,.1f} km.',
        'Magnitudes measure lunar diameters, not area fractions. RA / Dec: geocentric J2000 equatorial degrees.',
        'Instantaneous geometric model: light-time and detailed oblate-Earth shadow are not included.',
        'Original calculations, chart design, and drawing code: Star Almanack. Positional input: JPL DE440s.',
        'Provisional model results. Contact CSV and complete chart coordinates accompany the event page.'
    ]
    for i,note in enumerate(notes): text(50,1720+i*23,note,17)
    return ''.join(out)+'</svg>'

