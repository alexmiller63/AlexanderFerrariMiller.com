#!/usr/bin/env python3
"""Populate 2026 weekly Solar-System ephemerides from JPL Horizons."""
from __future__ import annotations
import csv,json,re,urllib.parse,urllib.request
from datetime import date,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; HORIZONS_API="https://ssd.jpl.nasa.gov/api/horizons.api"; YEAR=2026; SIGNS="♈♉♊♋♌♍♎♏♐♑♒♓"
TARGETS=[("☉ Sun","sun","10"),("☽ Moon","moon","301"),("☿ Mercury","mercury","199"),("♀ Venus","venus","299"),("♂ Mars","mars","499"),("⚳ Ceres","ceres","1;"),("♃ Jupiter","jupiter","599"),("♄ Saturn","saturn","699"),("♅ Uranus","uranus","799"),("♆ Neptune","neptune","899"),("♇ Pluto","pluto","999")]
def week_count(y): return date(y,12,28).isocalendar().week
def horizons_ecliptic(command):
 c=week_count(YEAR); first=date.fromisocalendar(YEAR,1,1); last=date.fromisocalendar(YEAR,c,1); p={"format":"json","COMMAND":f"'{command}'","OBJ_DATA":"'NO'","MAKE_EPHEM":"'YES'","EPHEM_TYPE":"'OBSERVER'","CENTER":"'500@399'","START_TIME":f"'{first.isoformat()} 00:00'","STOP_TIME":f"'{(last+timedelta(days=1)).isoformat()} 00:00'","STEP_SIZE":"'7 d'","QUANTITIES":"'31'","CSV_FORMAT":"'YES'","ANG_FORMAT":"'DEG'","CAL_FORMAT":"'CAL'","TIME_DIGITS":"'SECONDS'"}; req=urllib.request.Request(HORIZONS_API+'?'+urllib.parse.urlencode(p),headers={"User-Agent":"Star-Almanack/2026"}); payload=json.load(urllib.request.urlopen(req,timeout=90)); text=payload.get('result',''); lines=text.splitlines(); h=next(x for x in lines if 'ObsEcLon' in x and 'ObsEcLat' in x); head=[x.strip() for x in next(csv.reader([h]))]; li,bi=head.index('ObsEcLon'),head.index('ObsEcLat'); vals=[]
 for line in lines[lines.index('$$SOE')+1:lines.index('$$EOE')]:
  if line.strip(): r=next(csv.reader([line])); vals.append((float(r[li].strip()),float(r[bi].strip())))
 if len(vals)!=c: raise RuntimeError('Unexpected weekly row count')
 return vals
def zodiac(x):
 m=int(round((x%360)*60))%(360*60); s,w=divmod(m,1800); d,mi=divmod(w,60); return f'{SIGNS[s]} {d}°{mi:02d}′'
def beta(x):
 sg='+' if x>=0 else '−'; m=int(round(abs(x)*60)); d,mi=divmod(m,60); return f'β {sg}{d}°{mi:02d}′'
def render_ephemeris(monday,values):
 primary=TARGETS[:8]; extended=TARGETS[8:]
 def table(cols): return '<table class="ephemeris"><thead><tr>'+''.join(f'<th>{d}</th>' for d,_,_ in cols)+'</tr></thead><tbody><tr>'+''.join(f'<td>{values[k][0]}<br><small>{values[k][1]}</small></td>' for _,k,_ in cols)+'</tr></tbody></table>'
 return '<h3>Weekly Solar-System Ephemeris</h3>\n'+f'<p><strong>Snapshot:</strong> {monday.strftime("%B")} {monday.day}, {monday.year} · 00:00 UTC</p>\n'+table(primary)+'\n<p><strong>Extended targets:</strong></p>\n'+table(extended)+'\n<p class="ephemeris-note"><strong>β</strong> = ecliptic latitude (+ north, − south).</p>'
def main():
 c=week_count(YEAR); g={}
 for _,k,cmd in TARGETS: print(f'Fetching {YEAR} {k} from JPL Horizons'); g[k]=horizons_ecliptic(cmd)
 pat=re.compile(r'<h3>Weekly Solar-System Ephemeris</h3>\s*<p><strong>Snapshot:</strong>.*?</p>\s*<table(?: class="ephemeris")?>.*?</table>\s*<p><strong>Extended targets:</strong></p>\s*<table(?: class="ephemeris")?>.*?</table>(?:\s*<p class="ephemeris-note">.*?</p>)?',re.DOTALL); changed=0
 for w in range(1,c+1):
  path=ROOT/'almanack'/str(YEAR)/f'W{w:02d}'/'index.html'; text=path.read_text(encoding='utf-8'); monday=date.fromisocalendar(YEAR,w,1); vals={k:(zodiac(g[k][w-1][0]),beta(g[k][w-1][1])) for _,k,_ in TARGETS}; new,n=pat.subn(lambda _:render_ephemeris(monday,vals),text,count=1)
  if n!=1: raise RuntimeError(f'Could not locate ephemeris block in {path.relative_to(ROOT)}')
  if new!=text: path.write_text(new,encoding='utf-8'); changed+=1
 print(f'Updated {changed} weekly pages for {YEAR}')
if __name__=='__main__': main()
