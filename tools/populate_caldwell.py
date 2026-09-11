#!/usr/bin/env python3
"""Populate Caldwell observing events into requested or discovered Star Almanack years."""
from __future__ import annotations
import csv,datetime as dt,re,sys
from collections import defaultdict
from pathlib import Path
from star_almanack_astronomy import best_visibility_occurrences_for_iso_year,declination_band,season_for
from star_almanack_objects import HTML_AID,observing_aid_for_magnitude
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/"Star-Almanack-Repo"; PUBLIC=ROOT/"almanack"; SOURCE_SITE=SRC/"site"
CATALOG=SRC/"caldwell-catalog.csv"; FINEST_OVERLAP=SRC/"finest-ngc-caldwell-overlap.csv"; ASTERISM_OVERLAP=SRC/"asterism-catalog-overlap.csv"
CONSTELLATIONS={"And":"Andromeda","Aps":"Apus","Aqr":"Aquarius","Ara":"Ara","Aur":"Auriga","Boo":"Boötes","CMa":"Canis Major","Cam":"Camelopardalis","Car":"Carina","Cas":"Cassiopeia","Cen":"Centaurus","Cep":"Cepheus","Cet":"Cetus","Cha":"Chamaeleon","Cir":"Circinus","Cnc":"Cancer","Col":"Columba","Com":"Coma Berenices","CrA":"Corona Australis","Cru":"Crux","Crv":"Corvus","CVn":"Canes Venatici","Cyg":"Cygnus","Del":"Delphinus","Dor":"Dorado","Dra":"Draco","For":"Fornax","Gem":"Gemini","Hor":"Horologium","Hya":"Hydra","Lac":"Lacerta","Leo":"Leo","Lyn":"Lynx","Mon":"Monoceros","Mus":"Musca","Nor":"Norma","Pav":"Pavo","Peg":"Pegasus","Per":"Perseus","Pup":"Puppis","Sco":"Scorpius","Scl":"Sculptor","Sex":"Sextans","Sgr":"Sagittarius","Tau":"Taurus","TrA":"Triangulum Australe","Tuc":"Tucana","Vel":"Vela","Vir":"Virgo","Vul":"Vulpecula"}
TYPE_LABELS={"OC":"open cluster","GC":"globular cluster","PN":"planetary nebula","BN":"bright nebula","DN":"dark nebula","SN":"supernova remnant","IG":"irregular galaxy","SG":"spiral galaxy","SaG":"spiral galaxy","SbG":"spiral galaxy","ScG":"spiral galaxy","SdG":"spiral galaxy","SBG":"barred spiral galaxy","SBbG":"barred spiral galaxy","SBcG":"barred spiral galaxy","E4G":"elliptical galaxy","E6G":"elliptical galaxy","dE4G":"dwarf elliptical galaxy","dE0G":"dwarf elliptical galaxy","PecG":"peculiar galaxy","SeyfertG":"Seyfert galaxy"}
def iso_label(day): y,w,d=day.isocalendar(); return f"{y}-W{w:02d}-{d}"
def years_present():
 years=set()
 for root in (PUBLIC,SOURCE_SITE):
  if root.exists():
   for p in root.iterdir():
    if p.is_dir() and re.fullmatch(r"20\d{2}",p.name) and any(p.glob("W??/index.html")): years.add(int(p.name))
 return tuple(sorted(years))
def requested_years():
 if len(sys.argv)==1:return years_present()
 try: years=tuple(dict.fromkeys(int(v) for v in sys.argv[1:]))
 except ValueError as exc: raise SystemExit("Years must be integers, e.g. 2025 2027") from exc
 if any(y<1 for y in years): raise SystemExit("Years must be positive integers")
 return years
def read_catalog():
 with CATALOG.open(newline="",encoding="utf-8") as h: rows=list(csv.DictReader(h))
 if len(rows)!=109 or {r["caldwell"] for r in rows}!={f"C{i}" for i in range(1,110)}: raise RuntimeError("Caldwell catalog identifiers are incomplete or duplicated")
 return rows
def finest_caldwell_ids():
 with FINEST_OVERLAP.open(newline="",encoding="utf-8") as h: rows=list(csv.DictReader(h))
 ids={r["caldwell"] for r in rows}
 if len(rows)!=33 or len(ids)!=33: raise RuntimeError("Finest NGC/Caldwell overlap must contain 33 unique Caldwell identities")
 return ids
def asterism_catalog_ids():
 with ASTERISM_OVERLAP.open(newline="",encoding="utf-8") as h: return {r["catalog"].strip().upper() for r in csv.DictReader(h) if r.get("catalog")}
def visibility_rows(rows,year):
 out=[]
 for row in rows:
  for instant,day in best_visibility_occurrences_for_iso_year(float(row["ra_h"]),year):
   record=dict(row); record["best_instant_utc"]=instant.strftime("%Y-%m-%d %H:%M"); record["best_date"]=day.isoformat(); record["iso"]=iso_label(day); out.append(record)
 return out
def write_visibility(rows,year):
 path=SRC/"generated"/f"caldwell-visibility-{year}.csv"; path.parent.mkdir(parents=True,exist_ok=True)
 if not rows: raise RuntimeError(f"No Caldwell visibility rows generated for ISO year {year}")
 with path.open("w",newline="",encoding="utf-8") as h: w=csv.DictWriter(h,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def calendar_label(record,finest_ids,asterism_ids):
 cid=record["caldwell"].strip(); catalog=record.get("catalog","").strip(); name=record.get("name","").strip(); object_type=TYPE_LABELS.get(record.get("type","").strip(),"deep-sky object"); constellation=CONSTELLATIONS.get(record.get("con","").strip(),record.get("con","").strip())
 identity=[cid]
 for value in (catalog,name):
  if value and value.casefold() not in {x.casefold() for x in identity}: identity.append(value)
 head=", ".join(identity)+f", {object_type}"
 if cid in asterism_ids: head+=" (also an asterism)"
 head+=f" in {constellation}"
 day=dt.date.fromisoformat(record["best_date"]); magnitude=record.get("mag","").strip(); aid=observing_aid_for_magnitude(magnitude); glyph=HTML_AID[aid] if aid is not None else ""; observing=" ".join(p for p in (glyph,f"V {magnitude}" if magnitude else "") if p)
 parts=[head]
 if observing: parts.append(f'<span class="visibility-magnitude">{observing}</span>')
 if cid in finest_ids: parts.append("Finest NGC")
 parts.append(f"{declination_band(record['dec_deg'])} {season_for(day)}"); return " — ".join(parts)
def events_for(rows,finest_ids,asterism_ids):
 events=defaultdict(list)
 for record in rows: events[dt.date.fromisoformat(record["best_date"])].append(calendar_label(record,finest_ids,asterism_ids))
 return events
def pages_for_events(root,events):
 pages=[]
 for y in sorted({d.isocalendar().year for d in events}): pages.extend(sorted((root/str(y)).glob("W??/index.html")))
 return pages
def date_text(day): return f"{day:%a, %b} {day.day}, {day:%Y}"
def inject(root,events):
 changed=0
 for page in pages_for_events(root,events):
  text=page.read_text(encoding="utf-8"); original=text
  for day,labels in events.items():
   pattern=re.compile(rf"(<tr><td>{re.escape(date_text(day))}</td><td>.*?</td><td>)(.*?)(</td></tr>)"); match=pattern.search(text)
   if not match: continue
   keep=[] if match.group(2)=="—" else [i for i in match.group(2).split("<br>") if i]
   for label in labels:
    m=re.match(r"(C\d{1,3}),",label)
    if m:
     token=m.group(1); keep=[i for i in keep if not re.search(rf"(?:^|\(|\b){re.escape(token)}(?:\)|,|\b)",i)]
    keep.append(label)
   text=text[:match.start(2)]+("<br>".join(keep) if keep else "—")+text[match.end(2):]
  if text!=original: page.write_text(text,encoding="utf-8"); changed+=1
 return changed
def main():
 catalog=read_catalog(); finest_ids=finest_caldwell_ids(); asterism_ids=asterism_catalog_ids(); years=requested_years()
 if not years: raise RuntimeError("No generated Almanack years found")
 for year in years:
  rows=visibility_rows(catalog,year); write_visibility(rows,year); events=events_for(rows,finest_ids,asterism_ids); s=inject(SOURCE_SITE,events); p=inject(PUBLIC,events); print(f"{year}: Caldwell C1-C109 ISO-year occurrences; {len(finest_ids)} also Finest NGC; updated {s} source + {p} public pages")
if __name__=="__main__": main()
