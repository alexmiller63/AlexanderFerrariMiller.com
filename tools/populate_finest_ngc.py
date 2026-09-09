#!/usr/bin/env python3
"""Populate Finest NGC-only observing events into requested or discovered Almanack years.

Precedence is Messier -> Caldwell -> Finest NGC. Finest NGC objects already
represented by Messier or Caldwell are not emitted a second time. Caldwell
cross-membership is rendered by populate_caldwell.py.
"""
from __future__ import annotations

import csv
import datetime as dt
import re
import sys
from collections import defaultdict
from pathlib import Path

import populate_fixed_sky as fixed

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
PUBLIC = ROOT / "almanack"
SOURCE_SITE = SRC / "site"
CATALOG = SRC / "finest-ngc-catalog.csv"
CALDWELL = SRC / "finest-ngc-caldwell-overlap.csv"

CONSTELLATIONS = {
 "And":"Andromeda","Aqr":"Aquarius","Ari":"Aries","Aur":"Auriga","Boo":"Boötes","CMa":"Canis Major",
 "Cam":"Camelopardalis","Cas":"Cassiopeia","Cet":"Cetus","Com":"Coma Berenices","Crv":"Corvus",
 "CVn":"Canes Venatici","Cyg":"Cygnus","Dra":"Draco","Eri":"Eridanus","Gem":"Gemini","Her":"Hercules",
 "Hya":"Hydra","Leo":"Leo","LMi":"Leo Minor","Mon":"Monoceros","Ori":"Orion","Peg":"Pegasus",
 "Per":"Perseus","Pup":"Puppis","Scl":"Sculptor","Sex":"Sextans","Sgr":"Sagittarius","Tau":"Taurus",
 "UMa":"Ursa Major","Vir":"Virgo"
}
TYPE_LABELS={"OC":"open cluster","GC":"globular cluster","PN":"planetary nebula","EN":"emission nebula","RN":"reflection nebula","E/RN":"emission/reflection nebula","Gal":"galaxy"}
TELESCOPE_GLYPH = ('<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/telescope.svg" '
                   'alt="Telescope" aria-label="Telescope" style="height:1.15em;width:auto;vertical-align:-.18em">')

def years_present():
    years=set()
    for root in (PUBLIC,SOURCE_SITE):
        if root.exists():
            for p in root.iterdir():
                if p.is_dir() and re.fullmatch(r"20\d{2}",p.name) and any(p.glob("W??/index.html")):
                    years.add(int(p.name))
    return tuple(sorted(years))

def requested_years():
    if len(sys.argv)==1:
        return years_present()
    try:
        years=tuple(dict.fromkeys(int(value) for value in sys.argv[1:]))
    except ValueError as exc:
        raise SystemExit("Years must be integers, e.g. 2025 2027") from exc
    if any(year<1 for year in years):
        raise SystemExit("Years must be positive integers")
    return years

def rows(path):
    with path.open(newline="",encoding="utf-8") as f: return list(csv.DictReader(f))

def visibility_rows(catalog,year):
    out=[]
    for row in catalog:
        r=dict(row); instant,day=fixed.best_visibility(float(r["ra_h"]),year)
        r["best_instant_utc"]=instant.strftime("%Y-%m-%d %H:%M"); r["best_date"]=day.isoformat(); r["iso"]=fixed.iso_label(day); out.append(r)
    return out

def write_visibility(data,year):
    p=SRC/"generated"/f"finest-ngc-visibility-{year}.csv"; p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0])); w.writeheader(); w.writerows(data)

def label(r):
    catalog=r["catalog"].strip(); name=r.get("name","").strip(); typ=TYPE_LABELS.get(r.get("type","").strip(),"deep-sky object")
    con=CONSTELLATIONS.get(r.get("con","").strip(),r.get("con","").strip())
    head=f"{catalog}, {name}, {typ} in {con}" if name else f"{catalog}, {typ} in {con}"
    day=dt.date.fromisoformat(r["best_date"]); mag=r.get("mag","").strip(); observing=f"{TELESCOPE_GLYPH} V {mag}" if mag else TELESCOPE_GLYPH
    return f'{head} — {observing} — Finest NGC — {fixed.declination_band(r["dec_deg"])} {fixed.season_for(day)}'

def events_for(data):
    e=defaultdict(list)
    for r in data: e[dt.date.fromisoformat(r["best_date"])].append(label(r))
    return e

def inject(root,year,events):
    changed=0
    for page in sorted((root/str(year)).glob("W??/index.html")):
        text=page.read_text(encoding="utf-8"); original=text
        for day,labels in events.items():
            date_text=day.strftime("%a, %b %d, %Y").replace(" 0"," ")
            pat=re.compile(rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)"); m=pat.search(text)
            if not m: continue
            keep=[] if m.group(2)=="—" else [x for x in m.group(2).split("<br>") if x]
            for item in labels:
                designation=item.split(",",1)[0]
                keep=[x for x in keep if not ("Finest NGC" in x and re.search(rf"\b{re.escape(designation)}\b",x))]
                keep.append(item)
            text=text[:m.start(2)]+("<br>".join(keep) if keep else "—")+text[m.end(2):]
        if text!=original: page.write_text(text,encoding="utf-8"); changed+=1
    return changed

def main():
    catalog=rows(CATALOG); overlap={r["finest_ngc"] for r in rows(CALDWELL)}
    unique=[r for r in catalog if r["finest_ngc"] not in overlap]
    if len(overlap)!=33: raise RuntimeError(f"Expected 33 Caldwell overlaps, found {len(overlap)}")
    years=requested_years()
    if not years: raise RuntimeError("No generated Almanack years found")
    for year in years:
        data=visibility_rows(unique,year); write_visibility(data,year); e=events_for(data)
        a=inject(SOURCE_SITE,year,e); b=inject(PUBLIC,year,e)
        print(f"{year}: {len(data)} Finest NGC physical rows after Caldwell precedence; updated {a} source + {b} public pages")

if __name__=="__main__": main()
