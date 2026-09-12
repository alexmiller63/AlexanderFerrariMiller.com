#!/usr/bin/env python3
"""Populate major Star Almanack meteor-shower maxima for requested years."""
from __future__ import annotations

import argparse
import json
import math
from datetime import date, timedelta
from pathlib import Path

from almanack_calendar import ensure_calendar_metadata, get_events, page_dates, set_events
from populate_calendar import horizons_longitudes, interpolate_time, unwrap

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Star-Almanack-Repo" / "site"
PUBLIC_ROOT = ROOT / "almanack"
DATA_ROOT = ROOT / "Star-Almanack-Repo" / "generated"
METEOR_GLYPH = '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/meteor-shower.svg" alt="Meteor shower" aria-label="Meteor shower">'
SHOWERS = (
    ("Quadrantids", 283.15, "Boötes", 120),("Lyrids", 32.32, "Lyra", 18),("η-Aquariids", 45.50, "Aquarius", 50),
    ("Southern δ-Aquariids", 128.00, "Aquarius", 25),("α-Capricornids", 128.00, "Capricornus", 5),("Perseids", 140.00, "Perseus", 100),
    ("Orionids", 208.00, "Orion", 20),("Leonids", 235.27, "Leo", 15),("Geminids", 262.20, "Gemini", 150),("Ursids", 270.70, "Ursa Minor", 10),
)
SHOWER_NAMES = tuple(name for name, *_ in SHOWERS)

def crossing(samples,target_deg,year):
    times=[t for t,_ in samples]; values=unwrap([lon for _,lon in samples])
    for k in range(int((values[0]-target_deg)//360)-1,int((values[-1]-target_deg)//360)+2):
        target=target_deg+360*k
        for i in range(len(values)-1):
            if values[i] <= target <= values[i+1]:
                ts=interpolate_time(times[i],values[i],times[i+1],values[i+1],target)
                if ts.year==year:return ts
                break
    raise RuntimeError(f"No {year} solar-longitude crossing for {target_deg}°")

def longitude_at(samples,ts):
    for i in range(len(samples)-1):
        t0,lon0=samples[i]; t1,lon1=samples[i+1]
        if t0<=ts<=t1:
            delta=((lon1-lon0+180)%360)-180; fraction=0 if t1==t0 else (ts-t0).total_seconds()/(t1-t0).total_seconds(); return (lon0+delta*fraction)%360
    raise RuntimeError(f"Timestamp {ts.isoformat()} outside ephemeris sample range")

def moon_context(sun,moon,ts):
    elongation=abs(((longitude_at(moon,ts)-longitude_at(sun,ts)+180)%360)-180); illumination=(1-math.cos(math.radians(elongation)))/2; percent=int(round(illumination*100))
    interference="little moonlight interference" if illumination<.20 else "moderate moonlight interference" if illumination<.50 else "substantial moonlight interference" if illumination<.80 else "strong moonlight interference"
    return percent,interference

def observing_guidance(p):
    base="Use a dark site, allow 20–30 minutes for dark adaptation, and observe with the unaided eye."
    return base+(" Put the Moon behind a building, tree, or other obstruction and watch the darkest open sky." if p>=50 else " Watch a broad area of sky rather than staring directly at the radiant.")

def shower_events(year):
    start=date(year,1,1)-timedelta(days=10); stop=date(year+1,1,1)+timedelta(days=10); sun=horizons_longitudes("10",start,stop); moon=horizons_longitudes("301",start,stop); events=[]
    for name,lon,constellation,zhr in SHOWERS:
        ts=crossing(sun,lon,year); mp,interference=moon_context(sun,moon,ts); events.append((name,lon,constellation,zhr,ts,mp,interference))
    return events

def calendar_label(e):
    name,_,constellation,zhr,_,mp,interference=e
    return f"{METEOR_GLYPH} {name} peak · radiant in {constellation} · expected ZHR ≈ {zhr} · Moon {mp}% illuminated: {interference} · {observing_guidance(mp)}"

def patch_page(path,additions):
    if not path.exists(): return False
    original=path.read_text(encoding="utf-8"); text=ensure_calendar_metadata(original,path)
    for d in page_dates(path):
        cell=get_events(text,d)
        if cell is None: raise RuntimeError(f"Missing machine-readable calendar row for {d} in {path}")
        existing=[x for x in cell.split("<br>") if x and x!="—"]; keep=[x for x in existing if not any(name in x and "peak" in x for name in SHOWER_NAMES)]; merged=additions.get(d,[])+keep
        text,found=set_events(text,d,"<br>".join(merged) if merged else "—")
        if not found: raise RuntimeError(f"Could not update {d} in {path}")
    if text!=original:path.write_text(text,encoding="utf-8"); return True
    return False

def populate_year(year):
    maxima=shower_events(year); additions={}
    for e in maxima:additions.setdefault(e[4].date(),[]).append(calendar_label(e))
    DATA_ROOT.mkdir(parents=True,exist_ok=True)
    payload={"year":year,"basis":"Nominal maximum solar longitude with UTC crossing calculated from JPL Horizons apparent geocentric ecliptic-of-date solar longitude; Moon illumination calculated from Sun-Moon elongation at maximum","showers":[{"name":n,"solar_longitude_deg":lon,"radiant_constellation":c,"expected_zhr":z,"utc":ts.isoformat().replace("+00:00","Z"),"moon_illumination_percent":mp,"moon_interference":i,"observing_guidance":observing_guidance(mp),"calendar_label":calendar_label((n,lon,c,z,ts,mp,i))} for n,lon,c,z,ts,mp,i in maxima]}
    (DATA_ROOT/f"meteor-showers-{year}.json").write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    changed=0
    for base in (SOURCE_ROOT,PUBLIC_ROOT):
        for path in sorted((base/str(year)).glob("W??/index.html")): changed+=int(patch_page(path,additions))
    print(f"{year}: {len(maxima)} shower maxima with radiant/ZHR/Moon/guidance details, {changed} pages updated")
    return changed

def parse_years():
    p=argparse.ArgumentParser(); p.add_argument("years",metavar="YEAR",type=int,nargs="+"); a=p.parse_args(); years=list(dict.fromkeys(a.years))
    for y in years:
        if not 1900<=y<=2100:p.error(f"YEAR must be between 1900 and 2100: {y}")
    return years

def main():
    years=parse_years(); total=sum(populate_year(y) for y in years); print(f"Updated {total} meteor-shower page files for: {' '.join(map(str,years))}")
if __name__=="__main__":main()
