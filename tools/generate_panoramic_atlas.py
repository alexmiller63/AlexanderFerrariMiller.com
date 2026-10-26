#!/usr/bin/env python3
"""Star Almanack 14-region seasonal atlas. Deterministic, offline SVG generation.

Season membership is assigned by each star's 21:00 local apparent solar-time
meridian-transit DATE, not by equal right-ascension quadrants.
"""
import argparse
import csv
import datetime as dt
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBLIQUITY = 23.4393
SEASONS = ("Spring", "Summer", "Autumn", "Winter")
GLYPHS = ("♈", "♋", "♎", "♑")
WIDTH, HEIGHT = 1200, 720

def solar_longitude(t):
    jd = (t - dt.datetime(2000, 1, 1, 12)).total_seconds()/86400 + 2451545
    T = (jd - 2451545)/36525
    L = (280.46646 + T*(36000.76983 + .0003032*T))%360
    M = math.radians((357.52911 + T*(35999.05029 - .0001537*T))%360)
    C = (1.914602 - T*(.004817 + .000014*T))*math.sin(M) + (.019993 - .000101*T)*math.sin(2*M) + .000289*math.sin(3*M)
    omega = math.radians(125.04 - 1934.136*T)
    return (L+C-.00569-.00478*math.sin(omega))%360

def solar_ra(t):
    lon = math.radians(solar_longitude(t))
    return math.atan2(math.cos(math.radians(OBLIQUITY))*math.sin(lon),math.cos(lon))%(2*math.pi)

def ingress(year, angle, month):
    lo = dt.datetime(year, month, 15)
    hi = lo + dt.timedelta(days=12)
    for _ in range(45):
        mid = lo + (hi-lo)/2
        if (solar_longitude(mid)-angle+360)%360 < 180:
            hi = mid
        else:
            lo = mid
    return hi

def boundaries(year):
    return [ingress(year, a, m) for a,m in ((0,3),(90,6),(180,9),(270,12))]

def season_for_date(day, starts):
    for i in range(3,-1,-1):
        if day >= starts[i].date():
            return SEASONS[i]
    return "Winter"

def transit_day(ra_hours, year):
    """Find calendar date whose 21:00 apparent solar meridian RA is closest.

    The Sun's hour angle at 21:00 apparent solar time is +9h. Evaluate each
    UTC date at 12:00 as the date label; the annual sky repeats cyclically.
    """
    ra = math.radians(ra_hours*15)
    best = None
    for n in range(365 + (year%4==0 and (year%100!=0 or year%400==0))):
        day = dt.date(year,1,1)+dt.timedelta(days=n)
        t = dt.datetime.combine(day,dt.time(12))
        lst = (solar_ra(t)+math.radians(135))%(2*math.pi)
        delta = abs(math.atan2(math.sin(lst-ra),math.cos(lst-ra)))
        if best is None or delta < best[0]:
            best = (delta,day)
    return best[1]

def band(dec):
    if dec >= 90-OBLIQUITY: return "Arctic"
    if dec >= OBLIQUITY: return "Northern"
    if dec >= -OBLIQUITY: return "Tropical"
    if dec > -(90-OBLIQUITY): return "Southern"
    return "Antarctic"

def views():
    return [("Arctic",None)] + [(b,s) for b in ("Northern","Tropical","Southern") for s in SEASONS] + [("Antarctic",None)]

def render(view, rows, output, year, starts):
    region,season = view
    title = region + (" "+season if season else "") 
    # RA horizontal, declination vertical. Use one continuous 0..24h frame
    # for reproducible positioning; stars outside the region are not plotted.
    left,right,top,bottom = 76,WIDTH-34,92,HEIGHT-75
    limits = {"Arctic":(90-OBLIQUITY,90),"Northern":(OBLIQUITY,90-OBLIQUITY),
              "Tropical":(-OBLIQUITY,OBLIQUITY),
              "Southern":(-(90-OBLIQUITY),-OBLIQUITY),
              "Antarctic":(-90,-(90-OBLIQUITY))}
    low,high = limits[region]
    def xy(ra,dec):
        return left+(ra%24)/24*(right-left),bottom-(dec-low)/(high-low)*(bottom-top)
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{html.escape(title)} celestial chart">',
         f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#071527"/>',
         f'<text x="{WIDTH/2}" y="39" text-anchor="middle" fill="white" font-size="27">{html.escape(title)} · {year}</text>',
         '<text x="600" y="66" text-anchor="middle" fill="#b9d5e6" font-size="15">Season by 21:00 apparent-solar transit date · RA/declination chart</text>']
    for hour in range(0,25,2):
        x=left+hour/24*(right-left)
        s += [f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="#28415c"/>',
              f'<text x="{x:.1f}" y="{bottom+23}" text-anchor="middle" fill="#b9d5e6" font-size="13">{hour}h</text>']
    for dec in range(-90,91,10):
        if low <= dec <= high:
            y=xy(0,dec)[1]
            s += [f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="#28415c"/>',
                  f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" fill="#b9d5e6" font-size="12">{dec}°</text>']
    if low<=0<=high:
        y=xy(0,0)[1]
        s.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="#65cbd6" stroke-width="2"/>')
    # Ecliptic: trace only where it crosses the chart's declination band.
    prev=None
    for n in range(1441):
        lon=math.radians(n/4)
        ra=math.atan2(math.cos(math.radians(OBLIQUITY))*math.sin(lon),math.cos(lon))%(2*math.pi)
        dec=math.degrees(math.asin(math.sin(math.radians(OBLIQUITY))*math.sin(lon)))
        p=xy(math.degrees(ra)/15,dec) if low<=dec<=high else None
        if p and prev and abs(p[0]-prev[0])<20:
            s.append(f'<line x1="{prev[0]:.1f}" y1="{prev[1]:.1f}" x2="{p[0]:.1f}" y2="{p[1]:.1f}" stroke="#efc36d" stroke-width="1.6"/>')
        prev=p
    for row in rows:
        if row["band"]!=region or (season and row["season"]!=season):continue
        x,y=xy(row["ra_h"],row["dec_deg"])
        r=max(1.4,4.8-row["mag"]*.8)
        s.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="#e5eefc"/>')
        if row["mag"]<1.5 and row["name"]:
            s.append(f'<text x="{x+7:.1f}" y="{y-7:.1f}" fill="#d0e1f3" font-size="12">{html.escape(row["name"])}</text>')
    s += ['<text x="600" y="696" text-anchor="middle" fill="#9bb8cc" font-size="13">Gold: ecliptic · Cyan: celestial equator · Star Almanack</text>','</svg>']
    output.write_text("\n".join(s)+"\n",encoding="utf-8")

def load_figure_geometry():
    """Reuse Star Almanack's adopted constellation paths and their catalog stars."""
    source = ROOT / "finder-geometry/martz-macrobert.json"
    geometry = json.loads(source.read_text(encoding="utf-8"))
    figures = []
    stars = {}
    for abbr, entry in geometry["constellations"].items():
        for path in entry.get("paths", []):
            vertices = []
            for point in path:
                try:
                    ra = float(point["ra_h"])
                    dec = float(point["dec_deg"])
                    mag = float(point.get("magnitude") or 6.5)
                except (KeyError, ValueError, TypeError):
                    continue
                key = (round(ra, 5), round(dec, 5))
                stars[key] = dict(name="", ra_h=ra, dec_deg=dec, mag=mag)
                vertices.append((ra, dec))
            if len(vertices) > 1:
                figures.append((abbr, vertices))
    return list(stars.values()), figures


def overlay_figures(output, view, figures, year, starts):
    """Insert clipped blue constellation segments in the SVG below the stars."""
    region, season = view
    limits = {"Arctic":(90-OBLIQUITY,90),"Northern":(OBLIQUITY,90-OBLIQUITY),
              "Tropical":(-OBLIQUITY,OBLIQUITY),
              "Southern":(-(90-OBLIQUITY),-OBLIQUITY),
              "Antarctic":(-90,-(90-OBLIQUITY))}
    low, high = limits[region]
    left,right,top,bottom = 76,WIDTH-34,92,HEIGHT-75
    # Liang-Barsky clipping in chart coordinates. Only draw segments whose
    # midpoint belongs to the chart's season; preserve unclipped geometry.
    def clip(a,b):
        x0,y0=a; x1,y1=b
        dx=x1-x0; dy=y1-y0
        t0,t1=0.,1.
        for p,q in ((-dx,x0-left),(dx,right-x0),(-dy,y0-top),(dy,bottom-y0)):
            if abs(p)<1e-12:
                if q<0:return None
                continue
            t=q/p
            if p<0:t0=max(t0,t)
            else:t1=min(t1,t)
            if t0>t1:return None
        return ((x0+t0*dx,y0+t0*dy),(x0+t1*dx,y0+t1*dy))
    strokes=[]
    for abbr, vertices in figures:
        for (ra0,dec0),(ra1,dec1) in zip(vertices,vertices[1:]):
            if abs(ra1-ra0)>12:continue
            mid_ra=(ra0+ra1)/2
            if season and season_for_date(transit_day(mid_ra,year),starts)!=season:continue
            a=(left+ra0/24*(right-left),bottom-(dec0-low)/(high-low)*(bottom-top))
            b=(left+ra1/24*(right-left),bottom-(dec1-low)/(high-low)*(bottom-top))
            segment=clip(a,b)
            if segment:
                (x0,y0),(x1,y1)=segment
                strokes.append(f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" stroke="#5c8fe8" stroke-width="1.8" opacity=".85"/>')
    svg=output.read_text(encoding="utf-8")
    # Place lines behind stars but in front of the coordinate grid.
    marker='<text x="600" y="696"'
    svg=svg.replace(marker, "\\n".join(strokes)+"\\n"+marker)
    output.write_text(svg,encoding="utf-8")
    return len(strokes)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--year",type=int,default=2026)
    p.add_argument("--output",type=Path,default=ROOT/"star-almanack/chart-library/panoramic")
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    starts=boundaries(args.year)
    with (ROOT/"bright-stars-2mag.csv").open(encoding="utf-8",newline="") as f:
        catalog=list(csv.DictReader(f))
    extra_stars, figures = load_figure_geometry()\n    catalog.extend(extra_stars)\n    rows=[]
    for star in catalog:
        try:
            ra=float(star["ra_h"]); dec=float(star["dec_deg"])
            mag=float(star.get("representative_vmax",star.get("mag")))
        except (KeyError,ValueError,TypeError):continue
        day=transit_day(ra,args.year)
        rows.append(dict(name=star.get("proper",""),ra_h=ra,dec_deg=dec,mag=mag,
                         transit_date=day.isoformat(),band=band(dec),season=season_for_date(day,starts)))
    manifest={"year":args.year,"model":"season-by-21h-transit-date",
              "catalog":"bright-stars-2mag.csv",
              "season_ingresses_utc":[x.isoformat()+"Z" for x in starts],
              "season_start_dates":[x.date().isoformat() for x in starts],
              "projection":"equatorial rectangular RA/declination",
              "note":"Seasonal membership is date-based; horizontal RA extent is not forced to match season duration.",
              "views":[]}
    for region,season in views():
        key="-".join(x.lower() for x in (region,season) if x)
        name=f"{key}-{args.year}.svg"
        selected=[r for r in rows if r["band"]==region and (season is None or r["season"]==season)]
        render((region,season),rows,args.output/name,args.year,starts)\n        segments=overlay_figures(args.output/name,(region,season),figures,args.year,starts)
        manifest["views"].append({"region":region,"season":season,"file":name,"stars":len(selected),"figure_segments":segments})
    (args.output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print("Generated",len(manifest["views"]),"regional charts;",len(rows),"catalog stars")

if __name__=="__main__":
    main()
