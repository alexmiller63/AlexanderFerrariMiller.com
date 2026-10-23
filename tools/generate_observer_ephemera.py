#!/usr/bin/env python3
"""Topocentric Solar System ephemeris and numerical rise/set for a UTC civil date."""
import argparse, html, json, math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from skyfield.api import wgs84
from skyfield.framelib import ecliptic_frame
from star_almanack_ephemeris import StarAlmanackEphemeris

UTC=timezone.utc
BODIES=("sun","moon","mercury","venus","mars","ceres","jupiter","saturn","uranus","neptune","pluto")
def stamp(d): return d.isoformat(timespec="seconds").replace("+00:00","Z")
def horizon(body): return {"sun":-0.8333,"moon":-0.3}.get(body,-0.5667)

def calculate(instant, latitude, longitude, elevation):
    if not 1900<=instant.year<=2100: raise ValueError("Ceres source kernel covers 1900 through 2100 only")
    if not -90<=latitude<=90 or not -180<=longitude<=180: raise ValueError("Invalid latitude or longitude")
    engine=StarAlmanackEphemeris()
    observer=engine.earth+wgs84.latlon(latitude,longitude,elevation_m=elevation)
    day=instant.replace(hour=0,minute=0,second=0,microsecond=0)
    results=[]
    for body in BODIES:
        target=engine._body(body)
        def apparent(dt): return observer.at(engine.ts.from_datetime(dt)).observe(target).apparent()
        obj=apparent(instant)
        ra,dec,dist=obj.radec()
        lat,lon,_=obj.frame_latlon(ecliptic_frame)
        alt,az,_=obj.altaz()
        def offset(dt):
            altitude,_,_=apparent(dt).altaz()
            return float(altitude.degrees)-horizon(body)
        times=[day+timedelta(minutes=10*i) for i in range(145)]
        heights=[offset(t) for t in times]
        events=[]
        for i in range(144):
            fa,fb=heights[i],heights[i+1]
            if fa*fb>=0: continue
            a,b=times[i],times[i+1]
            for _ in range(20):
                m=a+(b-a)/2
                fm=offset(m)
                if fa*fm<=0: b=m
                else: a,fa=m,fm
            events.append({"type":"rise" if heights[i]<0 else "set","utc":stamp(a+(b-a)/2)})
        status="crossings" if events else ("always above horizon" if all(v>0 for v in heights) else "always below horizon" if all(v<0 for v in heights) else "no crossing resolved")
        results.append({"body":body,"ra_hours":round(float(ra.hours),8),"dec_deg":round(float(dec.degrees),7),
                        "ecliptic_longitude_deg":round(float(lon.degrees)%360,7),
                        "ecliptic_latitude_deg":round(float(lat.degrees),7),
                        "distance_au":round(float(dist.au),9),"altitude_deg":round(float(alt.degrees),6),
                        "azimuth_deg":round(float(az.degrees),6),"rise_set":{"state":status,"events":events}})
        print("COMPUTED",body,len(events),"horizon crossings",flush=True)
    return {"instant_utc":stamp(instant),"rise_set_utc_date":day.date().isoformat(),
            "observer":{"latitude":latitude,"longitude":longitude,"elevation_m":elevation},
            "source":"local DE440s and Ceres JPL/NAIF source SPKs via Skyfield",
            "precision":"provisional; atmospheric refraction, terrain, weather and grazing events not validated",
            "notes":["Coordinates are topocentric apparent.","Rise/set belong to UTC calendar date (not local date).",
                     "Continuous positions are resampled and horizon crossings bisected.",
                     "Earth is the observing origin and intentionally omitted from the body list."],
            "bodies":results}

def render(data):
    rows=[]
    for r in data["bodies"]:
        crossings="<br>".join(html.escape(x["type"]+" "+x["utc"]) for x in r["rise_set"]["events"])
        vals=[r["body"].title(),r["ra_hours"],r["dec_deg"],r["ecliptic_longitude_deg"],r["altitude_deg"]]
        rows.append("<tr>"+"".join("<td>"+html.escape(str(x))+"</td>" for x in vals)+"<td>"+(crossings or html.escape(r["rise_set"]["state"]))+"</td></tr>")
    return "<!doctype html><html lang='en'><meta charset='utf-8'><title>Star Almanack Ephemera</title><style>body{font:1rem/1.5 system-ui;background:#102039;color:white;margin:2rem}table{border-collapse:collapse}td,th{padding:.5rem;border:1px solid #9aa}</style><h1>Observer Ephemera</h1><p>"+html.escape(data["instant_utc"])+" · "+html.escape(str(data["observer"]))+"</p><table><tr><th>Body</th><th>RA (h)</th><th>Dec (°)</th><th>Ecliptic λ (°)</th><th>Altitude (°)</th><th>Rise/set UTC</th></tr>"+"".join(rows)+"</table><p>"+html.escape(data["precision"])+"</p></html>"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--instant",required=True,help="ISO 8601 instant, with Z or UTC offset")
    p.add_argument("--latitude",required=True,type=float)
    p.add_argument("--longitude",required=True,type=float)
    p.add_argument("--elevation-m",default=0.,type=float)
    p.add_argument("--output",default="generated/ephemera",type=Path)
    a=p.parse_args()
    dt=datetime.fromisoformat(a.instant.replace("Z","+00:00"))
    if dt.tzinfo is None: p.error("UTC offset required in instant")
    dt=dt.astimezone(UTC)
    if not math.isfinite(a.elevation_m) or not -500<=a.elevation_m<=10000: p.error("Invalid elevation")
    data=calculate(dt,a.latitude,a.longitude,a.elevation_m)
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"ephemera.json").write_text(json.dumps(data,indent=2)+"\n")
    (a.output/"ephemera.html").write_text(render(data))
    print("Saved ephemera.json and ephemera.html",flush=True)
if __name__=="__main__": main()
