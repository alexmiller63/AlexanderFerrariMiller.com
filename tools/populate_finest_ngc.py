#!/usr/bin/env python3
"""Populate Finest NGC-only observing events into requested or discovered Almanack years."""
from __future__ import annotations
import csv,datetime as dt,re,sys
from collections import defaultdict
from pathlib import Path
from almanack_calendar import ensure_calendar_metadata,get_events,set_events
from star_almanack_astronomy import best_visibility_occurrences_for_iso_year,declination_band,season_for
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/"Star-Almanack-Repo"; PUBLIC=ROOT/"almanack"; SOURCE_SITE=SRC/"site"; CATALOG=SRC/"finest-ngc-catalog.csv"; CALDWELL=SRC/"finest-ngc-caldwell-overlap.csv"
CONSTELLATIONS={"And":"Andromeda","Aqr":"Aquarius","Ari":"Aries","Aur":"Auriga","Boo":"Boötes","CMa":"Canis Major","Cam":"Camelopardalis","Cas":"Cassiopeia","Cet":"Cetus","Com":"Coma Berenices","Crv":"Corvus","CVn":"Canes Venatici","Cyg":"Cygnus","Dra":"Draco","Eri":"Eridanus","Gem":"Gemini","Her":"Hercules","Hya":"Hydra","Leo":"Leo","LMi":"Leo Minor","Mon":"Monoceros","Ori":"Orion","Peg":"Pegasus","Per":"Perseus","Pup":"Puppis","Scl":"Sculptor","Sex":"Sextans","Sgr":"Sagittarius","Tau":"Taurus","UMa":"Ursa Major","Vir":"Virgo"}
TYPE_LABELS={"OC":"open cluster","GC":"globular cluster","PN":"planetary nebula","EN":"emission nebula","RN":"reflection nebula","E/RN":"emission/reflection nebula","Gal":"galaxy"}
TELESCOPE_GLYPH='<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/telescope.svg" alt="Telescope" aria-label="Telescope" style="height:1.15em;width:auto;vertical-align:-.18em">'
def iso_label(day):y,w,wd=day.isocalendar(); return f"{y}-W{w:02d}-{wd}"
def years_present():
 years=set()
 for root in (PUBLIC,SOURCE_SITE):
  if root.exists():
   for path in root.iterdir():
    if path.is_dir() and re.fullmatch(r"20\d{2}",path.name) and any(path.glob("W??/index.html")):years.add(int(path.name))
 return tuple(sorted(years))
def requested_years():
 if len(sys.argv)==1:return years_present()
 try:years=tuple(dict.fromkeys(int(v) for v in sys.argv[1:]))
 except ValueError as exc:raise SystemExit("Years must be integers, e.g. 2025 2027") from exc
 if any(y<1 for y in years):raise SystemExit("Years must be positive integers")
 return years
def rows(path):
 with path.open(newline="",encoding="utf-8") as h:return list(csv.DictReader(h))
def visibility_rows(catalog,year):
 out=[]
 for row in catalog:
  for instant,day in best_visibility_occurrences_for_iso_year(float(row["ra_h"]),year):
   r=dict(row); r["best_instant_utc"]=instant.strftime("%Y-%m-%d %H:%M"); r["best_date"]=day.isoformat(); r["iso"]=iso_label(day); out.append(r)
 return out
def write_visibility(data,year):
 path=SRC/"generated"/f"finest-ngc-visibility-{year}.csv"; path.parent.mkdir(parents=True,exist_ok=True)
 if not data:raise RuntimeError(f"No Finest NGC visibility rows generated for ISO year {year}")
 with path.open("w",newline="",encoding="utf-8") as h:w=csv.DictWriter(h,fieldnames=list(data[0])); w.writeheader(); w.writerows(data)
def label(record):
 catalog=record["catalog"].strip(); name=record.get("name","").strip(); object_type=TYPE_LABELS.get(record.get("type","").strip(),"deep-sky object"); code=record.get("con","").strip(); constellation=CONSTELLATIONS.get(code,code); head=f"{catalog}, {name}, {object_type} in {constellation}" if name else f"{catalog}, {object_type} in {constellation}"; day=dt.date.fromisoformat(record["best_date"]); magnitude=record.get("mag","").strip(); observing=f"{TELESCOPE_GLYPH} V {magnitude}" if magnitude else TELESCOPE_GLYPH
 return f"{head} — {observing} — Finest NGC — {declination_band(record['dec_deg'])} {season_for(day)}"
def events_for(data):
 events=defaultdict(list)
 for r in data:events[dt.date.fromisoformat(r["best_date"])].append(label(r))
 return events
def pages_for_events(root,events):
 pages=[]
 for y in sorted({d.isocalendar().year for d in events}):pages.extend(sorted((root/str(y)).glob("W??/index.html")))
 return pages
def inject(root,events):
 changed=0
 for page in pages_for_events(root,events):
  original=page.read_text(encoding="utf-8"); text=ensure_calendar_metadata(original,page)
  for day,labels in events.items():
   cell=get_events(text,day)
   if cell is None:continue
   keep=[] if cell=="—" else [item for item in cell.split("<br>") if item]
   for item in labels:
    designation=item.split(",",1)[0]; keep=[existing for existing in keep if not ("Finest NGC" in existing and re.search(rf"\b{re.escape(designation)}\b",existing))]; keep.append(item)
   text,found=set_events(text,day,"<br>".join(keep) if keep else "—")
   if not found:raise RuntimeError(f"Could not update {day} in {page}")
  if text!=original:page.write_text(text,encoding="utf-8"); changed+=1
 return changed
def main():
 catalog=rows(CATALOG); overlap={r["finest_ngc"] for r in rows(CALDWELL)}; unique=[r for r in catalog if r["finest_ngc"] not in overlap]
 if len(overlap)!=33:raise RuntimeError(f"Expected 33 Caldwell overlaps, found {len(overlap)}")
 years=requested_years()
 if not years:raise RuntimeError("No generated Almanack years found")
 for year in years:
  data=visibility_rows(unique,year); write_visibility(data,year); events=events_for(data); s=inject(SOURCE_SITE,events); p=inject(PUBLIC,events); print(f"{year}: {len(data)} Finest NGC ISO-year occurrence rows after Caldwell precedence; updated {s} source + {p} public pages")
if __name__=="__main__":main()
