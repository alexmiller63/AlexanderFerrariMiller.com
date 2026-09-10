#!/usr/bin/env python3
"""Populate weekly Star Almanack Solar-System ephemerides from JPL Horizons."""
from __future__ import annotations
import argparse,csv,json,re,urllib.parse,urllib.request
from datetime import date,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; HORIZONS_API="https://ssd.jpl.nasa.gov/api/horizons.api"; SIGNS="♈♉♊♋♌♍♎♏♐♑♒♓"
TARGETS=[("☉ Sun","sun","10"),("☽ Moon","moon","301"),("☿ Mercury","mercury","199"),("♀ Venus","venus","299"),("♂ Mars","mars","499"),("♃ Jupiter","jupiter","599"),("♄ Saturn","saturn","699"),("⚳ Ceres","ceres","1;"),("♇ Pluto","pluto","999"),("♅ Uranus","uranus","799"),("♆ Neptune","neptune","899")]
VISIBILITY_GLYPHS={
 "naked_eye":'<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/eye.svg" alt="Naked eye" aria-label="Naked eye">',
 "binoculars":'<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/binoculars.svg" alt="Binoculars" aria-label="Binoculars">',
 "telescope":'<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/telescope.svg" alt="Telescope" aria-label="Telescope">',
}
def week_count(y): return date(y,12,28).isocalendar().week
def horizons_ephemeris(year,command):
 c=week_count(year); first=date.fromisocalendar(year,1,1); last=date.fromisocalendar(year,c,1); p={"format":"json","COMMAND":f"'{command}'","OBJ_DATA":"'NO'","MAKE_EPHEM":"'YES'","EPHEM_TYPE":"'OBSERVER'","CENTER":"'500@399'","START_TIME":f"'{first.isoformat()} 00:00'","STOP_TIME":f"'{(last+timedelta(days=1)).isoformat()} 00:00'","STEP_SIZE":"'7 d'","QUANTITIES":"'9,23,31'","CSV_FORMAT":"'YES'","ANG_FORMAT":"'DEG'","CAL_FORMAT":"'CAL'","TIME_DIGITS":"'SECONDS'"}
 req=urllib.request.Request(HORIZONS_API+'?'+urllib.parse.urlencode(p),headers={"User-Agent":"Star-Almanack/ephemeris"}); payload=json.load(urllib.request.urlopen(req,timeout=90)); text=payload.get("result",""); lines=text.splitlines(); h=next(x for x in lines if "ObsEcLon" in x and "ObsEcLat" in x); head=[x.strip() for x in next(csv.reader([h]))]
 def col(*names):
  for name in names:
   if name in head:return head.index(name)
  return None
 li,bi=col("ObsEcLon"),col("ObsEcLat"); mi=col("APmag","T-mag"); ei=col("S-O-T")
 vals=[]
 for line in lines[lines.index("$$SOE")+1:lines.index("$$EOE")]:
  if line.strip():
   r=next(csv.reader([line])); number=lambda i: float(r[i].strip()) if i is not None and r[i].strip() not in ("","n.a.") else None; vals.append((number(li),number(bi),number(mi),number(ei)))
 if len(vals)!=c: raise RuntimeError(f"Expected {c} weekly rows for {year} target {command}, found {len(vals)}")
 return vals
def zodiac(x):
 m=int(round((x%360)*60))%(360*60); s,w=divmod(m,1800); d,mi=divmod(w,60); return f"{SIGNS[s]} {d}°{mi:02d}′"
def beta(x):
 sg='+' if x>=0 else '−'; m=int(round(abs(x)*60)); d,mi=divmod(m,60); return f"β {sg}{d}°{mi:02d}′"
def current_visibility(magnitude,elongation):
 """Return practical observing aid; solar proximity can suppress visibility entirely."""
 if magnitude is None or elongation is None or elongation < 20.0:return None
 if magnitude <= 3.5:return "naked_eye"
 if magnitude <= 7.5:return "binoculars"
 return "telescope"
def visibility_html(magnitude,elongation):
 aid=current_visibility(magnitude,elongation)
 return VISIBILITY_GLYPHS[aid] if aid else ""
def render_ephemeris(monday,values):
 primary=TARGETS[:7]; extended=TARGETS[7:]
 def table(cols,show_visibility=False):
  headers=''.join(f'<th>{d}</th>' for d,_,_ in cols)
  positions=''.join(f'<td>{values[k][0]}<br><small>{values[k][1]}</small></td>' for _,k,_ in cols)
  rows='<tr>'+positions+'</tr>'
  if show_visibility: rows+='<tr class="ephemeris-visibility"><th scope="row">Current visibility</th>'+''.join(f'<td>{values[k][2]}</td>' for _,k,_ in cols)+'</tr>'
  return '<table class="ephemeris"><thead><tr>'+headers+'</tr></thead><tbody>'+rows+'</tbody></table>'
 return '<h3>Weekly Solar-System Ephemeris</h3>'+f'<p><strong>Snapshot:</strong> {monday.strftime("%B")} {monday.day}, {monday.year} · 00:00 UTC</p><p><strong>Naked Eye</strong></p>'+table(primary)+'<p><strong>Extended targets:</strong></p>'+table(extended,True)+'<p class="ephemeris-note"><strong>β</strong> = ecliptic latitude (+ north, − south). Current visibility combines visual magnitude with solar elongation; no glyph means not currently observable.</p>'
def update_year(year):
 c=week_count(year); g={}
 for _,k,cmd in TARGETS: print(f"Fetching {year} {k} from JPL Horizons"); g[k]=horizons_ephemeris(year,cmd)
 pat=re.compile(r'<h3>Weekly Solar-System Ephemeris</h3><p><strong>Snapshot:</strong>.*?</p>(?:<p><strong>Naked Eye</strong></p>)?<table class="ephemeris">.*?</table><p><strong>Extended targets:</strong></p><table class="ephemeris">.*?</table>(?:<p class="ephemeris-note">.*?</p>)?',re.DOTALL); changed=0
 for w in range(1,c+1):
  monday=date.fromisocalendar(year,w,1); vals={k:(zodiac(g[k][w-1][0]),beta(g[k][w-1][1]),visibility_html(g[k][w-1][2],g[k][w-1][3])) for _,k,_ in TARGETS}; replacement=render_ephemeris(monday,vals)
  for base in (ROOT/'almanack',ROOT/'Star-Almanack-Repo'/'site'):
   path=base/str(year)/f'W{w:02d}'/'index.html'; text=path.read_text(encoding='utf-8'); new,n=pat.subn(lambda _:replacement,text,count=1)
   if n!=1: raise RuntimeError(f"Could not locate ephemeris block in {path.relative_to(ROOT)}")
   if new!=text: path.write_text(new,encoding='utf-8'); changed+=1
 return changed
def parse_years():
 p=argparse.ArgumentParser(description="Populate weekly Solar-System ephemeris for one or more ISO years."); p.add_argument("years",nargs="+",type=int,help="ISO week-years to populate"); a=p.parse_args(); years=list(dict.fromkeys(a.years))
 for y in years:
  if not 1900<=y<=2100: p.error(f"YEAR must be between 1900 and 2100: {y}")
 return years
def main():
 years=parse_years(); total=0
 for y in years:
  changed=update_year(y); print(f"Updated {changed} weekly pages for {y}"); total+=changed
 print(f"Updated {total} weekly pages total")
if __name__=='__main__': main()
