#!/usr/bin/env python3
"""Render Messier calendar events in the Star Almanack canonical form."""
from __future__ import annotations
import csv,datetime as dt,json,re,sys
from collections import defaultdict
from pathlib import Path
import catalog_common_names as names
from star_almanack_astronomy import declination_band, season_for
from star_almanack_objects import HTML_AID, observing_aid_for_magnitude

ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/"Star-Almanack-Repo"; GENERATED=SRC/"generated"
PUBLIC=ROOT/"almanack"; SOURCE_SITE=SRC/"site"; FIXED=SRC/"fixed-objects.yaml"
EDITORIAL=json.loads((SRC/"messier-editorial.json").read_text(encoding="utf-8"))
ASTERISM_OVERLAP=SRC/"asterism-catalog-overlap.csv"; DEFAULT_YEARS=(2025,2026,2027)

def requested_years():
 if len(sys.argv)==1:return DEFAULT_YEARS
 try: years=tuple(dict.fromkeys(int(v) for v in sys.argv[1:]))
 except ValueError as exc: raise SystemExit("Years must be integers, e.g. 2025 2026 2027") from exc
 if any(y<1 for y in years): raise SystemExit("Years must be positive integers")
 return years

def asterism_catalog_ids():
 with ASTERISM_OVERLAP.open(newline="",encoding="utf-8") as h: rows=list(csv.DictReader(h))
 return {r["catalog"].strip().upper() for r in rows if r.get("catalog")}

def load_catalog():
 out={}; active=False
 for raw in FIXED.read_text(encoding="utf-8").splitlines():
  if raw=="messier:": active=True; continue
  if active and raw and not raw.startswith(" "): break
  if not active: continue
  m=re.match(r"\s*-\s*\[(.*)\]\s*$",raw)
  if not m: continue
  row=next(csv.reader([m.group(1)],skipinitialspace=True))
  if len(row)<9 or not re.fullmatch(r"M\d{1,3}",row[0].strip()): continue
  designation=row[0].strip().upper(); source_name=row[2].strip()
  if source_name.casefold()=="null": source_name=""
  edit=EDITORIAL["objects"].get(designation,{}); accepted=edit.get("accepted_name",source_name)
  if accepted is None: accepted=""
  out[designation]={"id":designation,"name":names.preferred_messier_name(designation,accepted),"type":edit.get("editorial_type",EDITORIAL["type_labels"].get(row[3].strip(),row[3].strip())),"con":EDITORIAL["constellation_labels"].get(row[4].strip(),row[4].strip()),"dec_deg":row[6].strip(),"mag":row[7].strip()}
 if len(out)!=110: raise RuntimeError(f"Expected 110 Messier objects, found {len(out)}")
 return out

def load_visibility(year):
 path=GENERATED/f"messier-visibility-{year}.csv"
 if not path.exists(): raise RuntimeError(f"Missing {path.relative_to(ROOT)}; run populate_fixed_sky.py before Messier standardization")
 with path.open(newline="",encoding="utf-8") as h: rows=list(csv.DictReader(h))
 by_id={r["messier"].strip().upper():r for r in rows}
 if len(by_id)!=110: raise RuntimeError(f"Expected 110 Messier visibility rows for {year}, found {len(by_id)}")
 return by_id

def label(record,day,asterism_ids):
 head=record["id"]
 if record["name"]: head+=f', {record["name"]}'
 head+=f', {record["type"]}'
 if record["id"] in asterism_ids: head+=' (also an asterism)'
 head+=f' in {record["con"]}'
 aid=observing_aid_for_magnitude(record["mag"]); glyph=HTML_AID[aid] if aid is not None else ""; magnitude=record["mag"]
 visibility=" ".join(p for p in (glyph,f"V {magnitude}" if magnitude else "") if p)
 visibility_html=f'<span class="visibility-magnitude">{visibility}</span>' if visibility else ""
 parts=[head];
 if visibility_html: parts.append(visibility_html)
 parts.append(f"{declination_band(record['dec_deg'])} {season_for(day)}")
 return " — ".join(parts)

def events(catalog,year):
 visibility=load_visibility(year); out=defaultdict(list); asterism_ids=asterism_catalog_ids()
 for designation in sorted(catalog,key=lambda v:int(v[1:])):
  if designation not in visibility: raise RuntimeError(f"Missing {designation} from generated Messier visibility for {year}")
  day=dt.date.fromisoformat(visibility[designation]["best_date"]); out[day].append(label(catalog[designation],day,asterism_ids))
 return out

def is_messier_event(item):
 plain=re.sub(r"<[^>]+>","",item).strip(); return bool(re.match(r"^(?:Messier\s+\d+\s+\(M\d+\)|M\d+\b|[^—]+\s+\(M\d+\),)",plain))

def pages_for_events(root,by_date):
 pages=[]
 for y in sorted({d.isocalendar().year for d in by_date}): pages.extend(sorted((root/str(y)).glob("W??/index.html")))
 return pages

def inject(root,by_date):
 changed=0
 for page in pages_for_events(root,by_date):
  text=page.read_text(encoding="utf-8"); original=text
  for day,labels in by_date.items():
   date_text=day.strftime("%a, %b %d, %Y"); pattern=re.compile(rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)"); match=pattern.search(text)
   if not match: continue
   keep=[] if match.group(2)=="—" else [item for item in match.group(2).split("<br>") if item and not is_messier_event(item)]
   keep.extend(labels); replacement="<br>".join(keep) if keep else "—"; text=text[:match.start(2)]+replacement+text[match.end(2):]
  if text!=original: page.write_text(text,encoding="utf-8"); changed+=1
 return changed

def main():
 catalog=load_catalog()
 for year in requested_years():
  by_date=events(catalog,year); s=inject(SOURCE_SITE,by_date); p=inject(PUBLIC,by_date)
  print(f"{year}: standardized 110 Messier events; updated {s} source + {p} public pages")
if __name__=="__main__": main()
