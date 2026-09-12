#!/usr/bin/env python3
"""Populate requested Almanack years with core asterism-center events."""
from __future__ import annotations
import argparse,csv,datetime as dt
from collections import defaultdict
from pathlib import Path
from almanack_calendar import ensure_calendar_metadata,get_events,set_events
from star_almanack_astronomy import declination_band, season_for
from star_almanack_objects import HTML_AID, observing_aid_for_magnitude
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/"Star-Almanack-Repo"; PUBLIC=ROOT/"almanack"; SOURCE_SITE=SRC/"site"; MEMBER_COORDS=SRC/"asterism-member-coordinates.csv"; CATALOG_OVERLAP=SRC/"asterism-catalog-overlap.csv"
def requested_years():
 p=argparse.ArgumentParser(description="Populate Star Almanack core asterism centers"); p.add_argument("years",metavar="YEAR",type=int,nargs="+"); a=p.parse_args(); years=list(dict.fromkeys(a.years))
 for y in years:
  if not 1900<=y<=2100:p.error(f"YEAR must be between 1900 and 2100: {y}")
 return years
def read_rows(year):
 path=SRC/f"asterism-geometry-{year}.csv"
 if not path.exists():raise SystemExit(f"Missing asterism geometry source for {year}: {path}")
 with path.open(newline="",encoding="utf-8") as f:rows=list(csv.DictReader(f))
 if len(rows)!=25:raise SystemExit(f"Expected 25 asterism rows for {year}, got {len(rows)}")
 if len({r['asterism'] for r in rows})!=25:raise SystemExit(f"Duplicate/missing asterism names for {year}")
 return rows
def catalog_overlaps():
 with CATALOG_OVERLAP.open(newline="",encoding="utf-8") as f:rows=list(csv.DictReader(f))
 names={r["asterism"].strip() for r in rows if r.get("asterism") and r.get("catalog")}
 if len(names)!=len(rows):raise SystemExit("Asterism/catalog overlap registry contains incomplete or duplicate identities")
 return names
def brightest_asterism_magnitudes():
 with MEMBER_COORDS.open(newline="",encoding="utf-8") as f:rows=list(csv.DictReader(f))
 brightest={}
 for r in rows:
  name=(r.get("asterism") or "").strip(); raw=(r.get("mag") or "").strip()
  if not name or not raw:continue
  try:mag=float(raw)
  except ValueError:continue
  if name not in brightest or mag<brightest[name]:brightest[name]=mag
 return brightest
def visibility_html(mag):
 aid=observing_aid_for_magnitude(str(mag))
 if aid is None:raise SystemExit(f"Could not derive observing aid for magnitude {mag}")
 return f'<span class="visibility-magnitude">{HTML_AID[aid]} V {mag:.1f}</span>'
def event_map(rows):
 e=defaultdict(list); brightest=brightest_asterism_magnitudes(); overlaps=catalog_overlaps()
 for r in rows:
  name=r['asterism']
  if name in overlaps:continue
  d=dt.date.fromisoformat(r["best_date"]); cls=f"{declination_band(r['centroid_dec_deg'])} {season_for(d)}"
  if name not in brightest:raise SystemExit(f"No stellar magnitude available for asterism {name}")
  e[d].append(f"{name} center — Asterism — {visibility_html(brightest[name])} — {cls}")
 return e
def pages_for_events(root,events):
 pages=[]
 for y in sorted({d.isocalendar().year for d in events}):pages.extend(sorted((root/str(y)).glob("W*/index.html")))
 return pages
def inject(root,events):
 changed=inserted=0
 for page in pages_for_events(root,events):
  original=page.read_text(encoding="utf-8"); text=ensure_calendar_metadata(original,page)
  for d,vals in events.items():
   cell=get_events(text,d)
   if cell is None:continue
   keep=[] if cell in ("—","") else [x for x in cell.split("<br>") if x and " center — Asterism — " not in x]
   before=len(keep)
   for v in vals:
    if v not in keep:keep.append(v)
   inserted+=len(keep)-before
   text,found=set_events(text,d,"<br>".join(keep) if keep else "—")
   if not found:raise SystemExit(f"Could not update {d} in {page}")
  if text!=original:page.write_text(text,encoding="utf-8"); changed+=1
 return changed,inserted
def validate(root,events):
 for d,vals in events.items():
  page=root/str(d.isocalendar().year)/f"W{d.isocalendar().week:02d}"/"index.html"
  text=ensure_calendar_metadata(page.read_text(encoding="utf-8"),page); cell=get_events(text,d)
  if cell is None:raise SystemExit(f"{root}: missing canonical calendar row for {d}")
  for v in vals:
   count=cell.split("<br>").count(v)
   if count!=1:raise SystemExit(f"{root}: expected {v!r} exactly once on {d} in {page}, found {count}")
def main():
 for year in requested_years():
  rows=read_rows(year); events=event_map(rows); overlaps=catalog_overlaps(); expected=len(rows)-len(overlaps); c1,i1=inject(SOURCE_SITE,events); c2,i2=inject(PUBLIC,events); validate(SOURCE_SITE,events); validate(PUBLIC,events); print(f"{year}: verified {expected} independent asterism centers; {len(overlaps)} catalog overlaps represented inline; inserted source={i1}, public={i2}; updated {c1} source + {c2} public pages")
if __name__=="__main__":main()
