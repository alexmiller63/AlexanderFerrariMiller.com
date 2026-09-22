#!/usr/bin/env python3
"""Populate fixed-sky visibility events for requested Almanack years."""
from __future__ import annotations
import csv
import re
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from almanack_calendar import CalendarEvent, ensure_calendar_metadata, get_events, set_events
from almanack_paths import ALMANACK_ROOT, calendar_pages
from star_almanack_astronomy import apparent_sun_ra_hours,best_visibility_occurrences_for_iso_year,solar_ra_occurrences_for_iso_year
from star_almanack_objects import AlmanackObject,ObservingAid,observing_aid_for_magnitude,render_html

ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT; PUBLIC=ALMANACK_ROOT; DEFAULT_YEARS=(2025,2026,2027)
REGIONS=SRC/"fixed-object-regions.yaml"
FIXED_OBJECTS=SRC/"fixed-objects.yaml"
FIXED_OBJECT_REGISTRY=SRC/"database"/"fixed-object-registry.json"
CATALOG_ENTRY_TARGETS=SRC/"database"/"catalog-entry-targets.json"
GREEK_BAYER={"Alp":"α","Bet":"β","Gam":"γ","Del":"δ","Eps":"ε","Zet":"ζ","Eta":"η","The":"θ","Iot":"ι","Kap":"κ","Lam":"λ","Mu":"μ","Nu":"ν","Xi":"ξ","Omi":"ο","Pi":"π","Rho":"ρ","Sig":"σ","Tau":"τ","Ups":"υ","Phi":"φ","Chi":"χ","Psi":"ψ","Ome":"ω"}

def requested_years():
    if len(sys.argv)==1:return DEFAULT_YEARS
    try:years=tuple(dict.fromkeys(int(x) for x in sys.argv[1:]))
    except ValueError as exc:raise SystemExit("Years must be integers, e.g. 2025 2026 2027") from exc
    if any(y<1 for y in years):raise SystemExit("Years must be positive integers")
    return years

def iso_label(d):y,w,wd=d.isocalendar(); return f"{y}-W{w:02d}-{wd}"
def read_csv(name):
    with (SRC/name).open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def load_regions():
    if not REGIONS.exists():
        raise RuntimeError(f"Missing {REGIONS.relative_to(ROOT)}; run the fixed-object region classifier first")
    data=yaml.safe_load(REGIONS.read_text(encoding="utf-8")) or {}
    return data.get("objects",{})
def load_messier_catalog():
    if not FIXED_OBJECTS.exists():
        raise RuntimeError(f"Missing {FIXED_OBJECTS.relative_to(ROOT)}")
    data=yaml.safe_load(FIXED_OBJECTS.read_text(encoding="utf-8")) or {}
    fields=(data.get("schema") or {}).get("messier") or []
    rows=data.get("messier") or []
    catalog={}
    for values in rows:
        row=dict(zip(fields,values))
        identity=str(row.get("id") or "").strip()
        if identity:
            catalog[identity]=row
    return catalog
REGION_OBJECTS=load_regions()
MESSIER_CATALOG=load_messier_catalog()

def load_catalog_entry_targets():
    if not CATALOG_ENTRY_TARGETS.exists():
        raise RuntimeError(f"Missing {CATALOG_ENTRY_TARGETS.relative_to(ROOT)}")
    data=json.loads(CATALOG_ENTRY_TARGETS.read_text(encoding="utf-8"))
    return {str(entry.get("catalog_entry_key") or "").strip(): entry for entry in data.get("catalog_entries", [])}
CATALOG_ENTRY_TARGETS_DATA=load_catalog_entry_targets()

def catalog_target_fixed_object_id(catalog, designation):
    """Return a direct physical-object ID when the catalog entry designates one.

    Catalog entries can legitimately represent regions or structured targets
    (for example M24 and M40). Those targets must not be fabricated into
    physical fixed-object identities merely to satisfy calendar metadata.
    """
    entry=CATALOG_ENTRY_TARGETS_DATA.get(f"{catalog.lower()}:{designation}")
    if not entry:return None
    direct=[]
    for target in entry.get("targets") or []:
        if target.get("target_kind") != "fixed_object":continue
        if target.get("relationship") not in {"designates"}:continue
        fixed_id=target.get("fixed_object_id")
        if fixed_id is not None:direct.append(int(fixed_id))
    if len(set(direct))>1:
        raise RuntimeError(f"Multiple direct fixed-object targets for {catalog}:{designation}: {direct}")
    return direct[0] if direct else None

def load_fixed_object_ids():
    data=json.loads(FIXED_OBJECT_REGISTRY.read_text(encoding="utf-8"))
    by_identifier={}
    for obj in data.get("fixed_objects",[]):
        if obj.get("status")!="active":continue
        fixed_id=int(obj["fixed_object_id"])
        for ident in obj.get("identifiers",[]):
            key=(str(ident.get("namespace") or "").strip().lower(),str(ident.get("value") or "").strip().lower())
            if key[0] and key[1]:by_identifier[key]=fixed_id
    return by_identifier
FIXED_OBJECT_IDS=load_fixed_object_ids()

def fixed_object_id(namespace,value):
    key=(namespace.strip().lower(),str(value or "").strip().lower())
    fixed_id=FIXED_OBJECT_IDS.get(key)
    if fixed_id is None:raise RuntimeError(f"Permanent fixed-object ID not found for {namespace}:{value}")
    return fixed_id
def canonical_occurrence(occurrences,year,identity):
    """Select the single annual event represented by one ISO week-year.

    ISO week-years legitimately contain a few dates from adjacent civil years.
    A single occurrence on one of those dates is valid and must be retained.
    The ambiguity arises only when an annual solar-RA crossing occurs twice in
    the same ISO-year page set (for example near both ends of a 53-week year).
    In that case, prefer the occurrence in the matching civil year.
    """
    occurrences=list(occurrences)
    if len(occurrences)==1:
        return occurrences[0]
    preferred=[pair for pair in occurrences if pair[1].year==year]
    if len(preferred)==1:
        return preferred[0]
    dates=", ".join(day.isoformat() for _,day in occurrences)
    raise RuntimeError(f"Could not select one canonical visibility occurrence for {identity} in ISO {year}; matching-civil-year={len(preferred)} among [{dates}]")
def redated(rows,iso_year):
    out=[]
    for row in rows:
        identity=(row.get("proper") or row.get("bayer") or row.get("messier") or row.get("hyg_id") or "object").strip()
        instant,day=canonical_occurrence(best_visibility_occurrences_for_iso_year(float(row["ra_h"]),iso_year),iso_year,identity)
        r=dict(row); r["best_instant_utc"]=instant.strftime("%Y-%m-%d %H:%M"); r["best_date"]=day.isoformat(); r["iso"]=iso_label(day); out.append(r)
    return out
def redated_preserving_2026_phase(rows,iso_year):
    out=[]
    for row in rows:
        canonical=dt.datetime.strptime(row["best_instant_utc"],"%Y-%m-%d %H:%M"); target=apparent_sun_ra_hours(canonical)
        identity=(row.get("messier") or row.get("proper") or row.get("bayer") or "object").strip()
        instant,day=canonical_occurrence(solar_ra_occurrences_for_iso_year(target,iso_year,date_mode="nearest"),iso_year,identity)
        r=dict(row); r["best_instant_utc"]=instant.strftime("%Y-%m-%d %H:%M"); r["best_date"]=day.isoformat(); r["iso"]=iso_label(day); out.append(r)
    return out
def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:raise RuntimeError(f"No visibility rows generated for {path.name}")
    with path.open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def display_bayer(r):
    bayer=r.get("bayer","").strip()
    if bayer in GREEK_BAYER:
        con=r.get("con","").strip(); return f"{GREEK_BAYER[bayer]} {con}" if con else GREEK_BAYER[bayer]
    return bayer
def in_milky_way(r):
    key=display_bayer(r)
    entry=REGION_OBJECTS.get("bayer",{}).get(key,{})
    return bool(entry.get("milky_way",{}).get("inside",False))
def star_event(r):
    proper=r.get("proper","").strip(); bayer=display_bayer(r); base=f"{proper} ({bayer})" if proper and bayer else (proper or bayer or f"{r.get('con','').strip()} star"); source_mag=(r.get("representative_vmax") or r.get("catalog_v") or r.get("mag") or "").strip()
    aid=observing_aid_for_magnitude(source_mag)
    catalog_id=(r.get("hyg_id") or r.get("hip") or r.get("hd") or bayer or "").strip()
    record=AlmanackObject(label=base,object_type="fixed_star",dec_deg=r["dec_deg"],best_date=dt.date.fromisoformat(r["best_date"]),observing_aid=aid,magnitude=source_mag,magnitude_display="none",catalog_id=catalog_id,provenance=(r.get("brightness_basis") or "").strip())
    label=render_html(record)+(" — in the Milky Way" if in_milky_way(r) else "")
    identifiers=[("hip",(r.get("hip") or "").strip()),("hd",(r.get("hd") or "").strip()),("bayer",bayer)]
    for namespace,value in identifiers:
        if not value:continue
        fixed_id=FIXED_OBJECT_IDS.get((namespace.strip().lower(),value.strip().lower()))
        if fixed_id is not None:return CalendarEvent(label,fixed_id,aid.value if aid else None)
    attempted=", ".join(f"{namespace}:{value}" for namespace,value in identifiers if value) or "none"
    raise RuntimeError(f"Permanent fixed-object identity not found for Calendar fixed star {base}; tried {attempted}")
def _messier_catalog_rows_for_annual_use():
    data=yaml.safe_load(FIXED_OBJECTS.read_text(encoding="utf-8")) or {}
    fields=(data.get("schema") or {}).get("messier") or []
    return [dict(zip(fields,row)) for row in data.get("messier") or []]

def page_date_map(year):
    from fixed_sky_annual import occurrences_for_iso_year
    occurrences=occurrences_for_iso_year(year)
    bayer=read_csv("expanded-bayer-visibility-2026.csv")
    bright=read_csv("bright-star-visibility-2026.csv")
    events=defaultdict(list); seen=set(); bayer_targets={}

    for r in bayer:
        identity=display_bayer(r).strip().lower()
        key=("expanded-bayer",f"{r.get('bayer','').strip()}:{r.get('con','').strip()}")
        if identity and key in occurrences:
            current=bayer_targets.get(identity)
            if current is None or (not (current.get("proper") or "").strip() and (r.get("proper") or "").strip()):
                bayer_targets[identity]=r

    for identity,r in bayer_targets.items():
        occurrence=occurrences.get(("expanded-bayer",f"{r.get('bayer','').strip()}:{r.get('con','').strip()}"))
        if occurrence is None:continue
        r=dict(r); r["best_date"]=occurrence["best_date"]; d=dt.date.fromisoformat(r["best_date"])
        key=(d,identity)
        if key not in seen:events[d].append(star_event(r)); seen.add(key)

    for r in bright:
        if r.get("new_non_alpha_beta","").lower()!="yes":continue
        key_name=(r.get("proper") or "").strip() or f"{r.get('bayer','').strip()}:{r.get('con','').strip()}"
        occurrence=occurrences.get(("bright-star",key_name))
        if occurrence is None:continue
        r=dict(r); r["best_date"]=occurrence["best_date"]; d=dt.date.fromisoformat(r["best_date"]); key=(d,key_name.lower())
        if key_name and key not in seen:events[d].append(star_event(r)); seen.add(key)

    for r in _messier_catalog_rows_for_annual_use():
        identity=r["id"].strip(); occurrence=occurrences.get(("messier",identity))
        if occurrence is None:continue
        d=dt.date.fromisoformat(occurrence["best_date"]); catalog=MESSIER_CATALOG.get(identity)
        if catalog is None:raise RuntimeError(f"Missing {identity} from {FIXED_OBJECTS.name} Messier catalog")
        if catalog.get("dec_deg") is None:raise RuntimeError(f"Missing declination for {identity} in {FIXED_OBJECTS.name}")
        events[d].append(CalendarEvent(render_html(AlmanackObject(label=identity,object_type="deep_sky",dec_deg=catalog["dec_deg"],best_date=d,observing_aid=ObservingAid.TELESCOPE)),catalog_target_fixed_object_id("messier",identity),ObservingAid.TELESCOPE.value))
    return events

def pages_for_events(root,events):
    pages=[]
    for iso_year in sorted({d.isocalendar().year for d in events}):pages.extend(calendar_pages(iso_year))
    return pages
def _event_identity(value):
    """Return a stable visible-text identity, ignoring HTML markup."""
    base = value.split(" — ", 1)[0]
    return re.sub(r"\\s+", " ", re.sub(r"<[^>]+>", "", base)).strip().lower()

def inject(root,year,events):
    changed=0
    for page in pages_for_events(root,events):
        original=page.read_text(encoding="utf-8"); text=ensure_calendar_metadata(original,page)
        for d,vals in events.items():
            cell=get_events(text,d)
            if cell is None:continue
            keep=[] if cell=="—" else [x for x in cell.split("<br>") if x]
            semantic=[]
            for v in vals:
                identity=_event_identity(v.html)
                keep=[x for x in keep if _event_identity(x) != identity]
                semantic.append(v)
            records=[CalendarEvent(x) for x in keep]+semantic
            text,found=set_events(text,d,records)
            if not found:raise RuntimeError(f"Could not update {d} in {page}")
        if text!=original:page.write_text(text,encoding="utf-8"); changed+=1
    return changed
def main():
    for year in requested_years():
        events=page_date_map(year); c2=inject(PUBLIC,year,events); print(f"{year}: canonical fixed-sky entries with observing glyph, declination band, season and Milky Way membership; updated {c2} public pages")
if __name__=="__main__":main()
