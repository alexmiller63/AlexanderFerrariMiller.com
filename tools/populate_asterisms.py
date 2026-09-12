#!/usr/bin/env python3
"""Populate requested Almanack years with core asterism-center events.

Asterism-center entries use the established pattern-visibility rule: the
brightest member star supplies both the V magnitude and the observing-aid class.

Catalog membership and asterism identity are different semantic dimensions. A
physical object such as the Pleiades may therefore appear once as a catalog
object (M45) and once as an asterism center. Catalog precedence still applies
within the mutually exclusive catalog classes (Messier/Caldwell/Finest NGC),
but it must not erase an independent asterism-center observance.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,re
from collections import defaultdict
from pathlib import Path

from star_almanack_astronomy import declination_band, season_for
from star_almanack_objects import HTML_AID, observing_aid_for_magnitude

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"Star-Almanack-Repo"
PUBLIC=ROOT/"almanack"
SOURCE_SITE=SRC/"site"
MEMBER_COORDS=SRC/"asterism-member-coordinates.csv"
CATALOG_OVERLAP=SRC/"asterism-catalog-overlap.csv"

def requested_years():
 p=argparse.ArgumentParser(description="Populate Star Almanack core asterism centers")
 p.add_argument("years",metavar="YEAR",type=int,nargs="+",help="Years to populate")
 a=p.parse_args(); years=list(dict.fromkeys(a.years))
 for y in years:
  if not 1900<=y<=2100: p.error(f"YEAR must be between 1900 and 2100: {y}")
 return years

def read_rows(year):
 path=SRC/f"asterism-geometry-{year}.csv"
 if not path.exists(): raise SystemExit(f"Missing asterism geometry source for {year}: {path}")
 with path.open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))
 if len(rows)!=25: raise SystemExit(f"Expected 25 asterism rows for {year}, got {len(rows)}")
 if len({r['asterism'] for r in rows})!=25: raise SystemExit(f"Duplicate/missing asterism names for {year}")
 return rows

def catalog_overlaps():
 """Return documented cross-identities for provenance/auditing only."""
 with CATALOG_OVERLAP.open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))
 names={r["asterism"].strip() for r in rows if r.get("asterism") and r.get("catalog")}
 if len(names)!=len(rows): raise SystemExit("Asterism/catalog overlap registry contains incomplete or duplicate identities")
 return names

def brightest_asterism_magnitudes():
 with MEMBER_COORDS.open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))
 brightest={}
 for r in rows:
  name=(r.get("asterism") or "").strip(); raw=(r.get("mag") or "").strip()
  if not name or not raw: continue
  try: mag=float(raw)
  except ValueError: continue
  if name not in brightest or mag<brightest[name]: brightest[name]=mag
 return brightest

def visibility_html(mag):
 aid=observing_aid_for_magnitude(str(mag))
 if aid is None: raise SystemExit(f"Could not derive observing aid for magnitude {mag}")
 return f'<span class="visibility-magnitude">{HTML_AID[aid]} V {mag:.1f}</span>'

def event_map(rows):
 e=defaultdict(list); brightest=brightest_asterism_magnitudes()
 for r in rows:
  name=r['asterism']
  d=dt.date.fromisoformat(r["best_date"])
  cls=f"{declination_band(r['centroid_dec_deg'])} {season_for(d)}"
  if name not in brightest: raise SystemExit(f"No stellar magnitude available for asterism {name}")
  e[d].append(f"{name} center — Asterism — {visibility_html(brightest[name])} — {cls}")
 return e

def date_pattern(d): return rf"{d.strftime('%a, %b ')}0?{d.day}, {d.year}"

def pages_for_events(root,events):
 pages=[]
 for y in sorted({d.isocalendar().year for d in events}):
  pages.extend(sorted((root/str(y)).glob("W*/index.html")))
 return pages

def inject(root,events):
 changed=inserted=0
 for page in pages_for_events(root,events):
  text=page.read_text(encoding="utf-8"); original=text
  # Remove all previously generated asterism-center rows before rebuilding them.
  text=re.sub(r"(?:<br>)?(?:✦ )?[^<]*? center — Asterism — .*?(?=<br>|</td>)","",text)
  text=text.replace("<td><br>","<td>").replace("<br></td>","</td>").replace("<br><br>","<br>")
  for d,vals in events.items():
   pat=re.compile(rf"(<tr><td>{date_pattern(d)}</td><td>.*?</td><td>)(.*?)(</td></tr>)")
   m=pat.search(text)
   if not m: continue
   keep=[] if m.group(2) in ("—","") else [x for x in m.group(2).split("<br>") if x]
   before=len(keep)
   for v in vals:
    if v not in keep: keep.append(v)
   inserted+=len(keep)-before
   text=text[:m.start(2)]+("<br>".join(keep) if keep else "—")+text[m.end(2):]
  if text!=original: page.write_text(text,encoding="utf-8"); changed+=1
 return changed,inserted

def validate(root,events):
 page_texts=[(p,p.read_text(encoding="utf-8")) for p in pages_for_events(root,events)]
 for d,vals in events.items():
  pat=re.compile(rf"<tr><td>{date_pattern(d)}</td><td>.*?</td><td>(.*?)</td></tr>")
  matches=[(p,m.group(1)) for p,text in page_texts for m in pat.finditer(text)]
  if len(matches)!=1: raise SystemExit(f"{root}: expected exactly one calendar row for {d}, found {len(matches)}")
  page,cell=matches[0]
  for v in vals:
   count=cell.split("<br>").count(v)
   if count!=1: raise SystemExit(f"{root}: expected {v!r} exactly once on {d} in {page}, found {count}")

def main():
 for year in requested_years():
  rows=read_rows(year); events=event_map(rows); overlaps=catalog_overlaps()
  c1,i1=inject(SOURCE_SITE,events); c2,i2=inject(PUBLIC,events)
  validate(SOURCE_SITE,events); validate(PUBLIC,events)
  print(f"{year}: verified {len(rows)} asterism centers; {len(overlaps)} also have catalog identities retained separately; inserted source={i1}, public={i2}; updated {c1} source + {c2} public pages")

if __name__=="__main__": main()
