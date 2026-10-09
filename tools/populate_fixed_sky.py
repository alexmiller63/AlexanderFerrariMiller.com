#!/usr/bin/env python3
"""Populate fixed-sky visibility events for requested Almanack years."""
from __future__ import annotations
import csv
import re
import datetime as dt
import json
import sys
from html import escape
from collections import defaultdict
from pathlib import Path

import yaml

from almanack_calendar import CalendarEvent, ensure_calendar_metadata, get_event_records, set_events
from almanack_paths import ALMANACK_ROOT, weekly_pages
from star_almanack_astronomy import apparent_sun_ra_hours,best_visibility_occurrences_for_iso_year,solar_ra_occurrences_for_iso_year
from star_almanack_objects import AlmanackObject,ObservingAid,observing_aid_for_magnitude,render_html
from fixed_sky_annual import ensure_coverage, occurrences_for_iso_year

ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT; PUBLIC=ALMANACK_ROOT; DEFAULT_YEARS=(2025,2026,2027)
REGIONS=SRC/"fixed-object-regions.yaml"
FIXED_OBJECTS=SRC/"fixed-objects.yaml"
FIXED_OBJECT_REGISTRY=SRC/"database"/"fixed-object-registry.json"
CATALOG_ENTRY_TARGETS=SRC/"database"/"catalog-entry-targets.json"
BRIGHT_VARIABLES=SRC/"bright-variable-reconciliation.csv"
GREEK_BAYER={"Alp":"α","Bet":"β","Gam":"γ","Del":"δ","Eps":"ε","Zet":"ζ","Eta":"η","The":"θ","Iot":"ι","Kap":"κ","Lam":"λ","Mu":"μ","Nu":"ν","Xi":"ξ","Omi":"ο","Pi":"π","Rho":"ρ","Sig":"σ","Tau":"τ","Ups":"υ","Phi":"φ","Chi":"χ","Psi":"ψ","Ome":"ω"}
GCVS_BAYER={"Alp":"alf","Bet":"bet","Gam":"gam","Del":"del","Eps":"eps","Zet":"zet","Eta":"eta","The":"the","Iot":"iot","Kap":"kap","Lam":"lam","Mu":"mu","Nu":"nu","Xi":"xi","Omi":"omi","Pi":"pi","Rho":"rho","Sig":"sig","Tau":"tau","Ups":"ups","Phi":"phi","Chi":"chi","Psi":"psi","Ome":"ome"}

def load_variable_stars():
    if not BRIGHT_VARIABLES.exists():
        raise RuntimeError(f"Missing {BRIGHT_VARIABLES.relative_to(ROOT)}")
    with BRIGHT_VARIABLES.open(newline="",encoding="utf-8") as f:
        return {row["name"].strip().lower(): row for row in csv.DictReader(f) if row.get("name")}
VARIABLE_STARS=load_variable_stars()

def variable_type_for_row(r):
    code=(r.get("bayer_code") or r.get("bayer") or "").strip(); con=(r.get("con") or "").strip(); match=re.fullmatch(r"([A-Za-z]{3})[- ]?(\d*)",code)
    if not match or not con:return ""
    stem=GCVS_BAYER.get(match.group(1).title())
    if not stem:return ""
    suffix=match.group(2); key=f"{stem}{(' ' + suffix) if suffix else ''} {con}".lower(); row=VARIABLE_STARS.get(key)
    return (row.get("variability_type") or "").strip() if row else ""

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
    if not REGIONS.exists():raise RuntimeError(f"Missing {REGIONS.relative_to(ROOT)}; run the fixed-object region classifier first")
    data=yaml.safe_load(REGIONS.read_text(encoding="utf-8")) or {}; return data.get("objects",{})
def load_messier_catalog():
    if not FIXED_OBJECTS.exists():raise RuntimeError(f"Missing {FIXED_OBJECTS.relative_to(ROOT)}")
    data=yaml.safe_load(FIXED_OBJECTS.read_text(encoding="utf-8")) or {}; fields=(data.get("schema") or {}).get("messier") or []; rows=data.get("messier") or []; catalog={}
    for values in rows:
        row=dict(zip(fields,values)); identity=str(row.get("id") or "").strip()
        if identity:catalog[identity]=row
    return catalog
REGION_OBJECTS=load_regions(); MESSIER_CATALOG=load_messier_catalog()

def load_catalog_entry_targets():
    if not CATALOG_ENTRY_TARGETS.exists():raise RuntimeError(f"Missing {CATALOG_ENTRY_TARGETS.relative_to(ROOT)}")
    data=json.loads(CATALOG_ENTRY_TARGETS.read_text(encoding="utf-8")); return {str(entry.get("catalog_entry_key") or "").strip():entry for entry in data.get("catalog_entries",[])}
CATALOG_ENTRY_TARGETS_DATA=load_catalog_entry_targets()

def catalog_target_fixed_object_id(catalog,designation):
    entry=CATALOG_ENTRY_TARGETS_DATA.get(f"{catalog.lower()}:{designation}")
    if entry:
        direct=[]
        for target in entry.get("targets") or []:
            if target.get("target_kind")!="fixed_object" or target.get("relationship") not in {"designates"}:continue
            fixed_id=target.get("fixed_object_id")
            if fixed_id is not None:direct.append(int(fixed_id))
        if len(set(direct))>1:raise RuntimeError(f"Multiple direct fixed-object targets for {catalog}:{designation}: {direct}")
        if direct:return direct[0]
    return FIXED_OBJECT_IDS.get((catalog.strip().lower(),designation.strip().lower()))

def load_fixed_object_ids():
    data=json.loads(FIXED_OBJECT_REGISTRY.read_text(encoding="utf-8")); by_identifier={}
    for obj in data.get("fixed_objects",[]):
        if obj.get("status")!="active":continue
        fixed_id=int(obj["fixed_object_id"])
        for ident in obj.get("identifiers",[]):
            key=(str(ident.get("namespace") or "").strip().lower(),str(ident.get("value") or "").strip().lower())
            if key[0] and key[1]:by_identifier[key]=fixed_id
    return by_identifier
FIXED_OBJECT_IDS=load_fixed_object_ids()

ADDITIONAL_CATALOGS = (
    ("caldwell", "caldwell-catalog.csv", "caldwell"),
    ("finest_ngc", "finest-ngc-catalog.csv", "finest_ngc"),
    ("special-star", "special-star-catalog.csv", "id"),
)

def special_fixed_object_id(row):
    """Resolve source identities; unregistered targets retain their catalog key.

    Sirius and Sirius B is a system observing target, not a synonym for Sirius A.
    """
    direct = FIXED_OBJECT_IDS.get(("special", row["id"].lower()))
    if direct is not None:
        return direct
    if row["id"] == "sirius-b":
        return None
    hip = str(row.get("hip") or "").strip()
    if hip:
        fixed_id = FIXED_OBJECT_IDS.get(("hip", hip))
        if fixed_id is None:
            raise RuntimeError(f"Unknown explicit HIP {hip} for special star {row['id']}")
        return fixed_id
    from object_identity import resolve_source_name
    try:
        return resolve_source_name(row["name"])
    except RuntimeError as exc:
        if "resolves to []" not in str(exc):
            raise
    return None

def catalog_event(source, row, day, fixed_id):
    if source == "special-star":
        label = escape(row["name"])
        if row.get("designation"):
            label += f' ({escape(row["designation"])})'
        aid = {"👁": ObservingAid.NAKED_EYE, "B": ObservingAid.BINOCULARS,
               "🔭": ObservingAid.TELESCOPE}.get(row["observing_aid"])
        if aid is None:
            label += " (variable brightness)"
        key = row["id"]
        kind = "fixed_star"
    else:
        key = row[source]
        designation = key if source == "caldwell" else f'Finest NGC {key}'
        label = escape(f'{designation} / {row["catalog"]}')
        if row.get("name"):
            label += f' · {escape(row["name"])}'
        aid, kind = ObservingAid.TELESCOPE, "deep_sky"
    record = AlmanackObject(label=label, object_type=kind, dec_deg=row["dec_deg"],
        best_date=day, observing_aid=aid, magnitude=row.get("mag", ""),
        magnitude_display="whole")
    return CalendarEvent(render_html(record), fixed_id, aid.value if aid else None,
                         None if fixed_id is not None else f"{source}:{key}")

def merge_same_targets(events):
    """One event per physical target per date, preserving catalog aliases."""
    merged = {}
    for index, event in enumerate(events):
        identity = (("fixed", event.fixed_object_id) if event.fixed_object_id is not None
                    else (("target", event.catalog_target_key) if event.catalog_target_key
                          else ("other", index)))
        if identity not in merged:
            merged[identity] = event
            continue
        old = merged[identity]
        alias = event.html.split(" — ", 1)[0]
        label, separator, details = old.html.partition(" — ")
        if alias not in label:
            label += " / " + alias
        merged[identity] = CalendarEvent(label + separator + details,
            old.fixed_object_id, old.observing_aid, old.catalog_target_key)
    return list(merged.values())

def fixed_object_id(namespace,value):
    key=(namespace.strip().lower(),str(value or "").strip().lower()); fixed_id=FIXED_OBJECT_IDS.get(key)
    if fixed_id is None:raise RuntimeError(f"Permanent fixed-object ID not found for {namespace}:{value}")
    return fixed_id
def canonical_occurrence(occurrences,year,identity):
    occurrences=list(occurrences)
    if len(occurrences)==1:return occurrences[0]
    preferred=[pair for pair in occurrences if pair[1].year==year]
    if len(preferred)==1:return preferred[0]
    dates=", ".join(day.isoformat() for _,day in occurrences); raise RuntimeError(f"Could not select one canonical visibility occurrence for {identity} in ISO {year}; matching-civil-year={len(preferred)} among [{dates}]")
def redated(rows,iso_year):
    out=[]
    for row in rows:
        identity=(row.get("proper") or row.get("bayer") or row.get("messier") or row.get("hyg_id") or "object").strip(); instant,day=canonical_occurrence(best_visibility_occurrences_for_iso_year(float(row["ra_h"]),iso_year),iso_year,identity); r=dict(row); r["best_instant_utc"]=instant.strftime("%Y-%m-%d %H:%M"); r["best_date"]=day.isoformat(); r["iso"]=iso_label(day); out.append(r)
    return out
def redated_preserving_2026_phase(rows,iso_year):
    out=[]
    for row in rows:
        canonical=dt.datetime.strptime(row["best_instant_utc"],"%Y-%m-%d %H:%M"); target=apparent_sun_ra_hours(canonical); identity=(row.get("messier") or row.get("proper") or row.get("bayer") or "object").strip(); instant,day=canonical_occurrence(solar_ra_occurrences_for_iso_year(target,iso_year,date_mode="nearest"),iso_year,identity); r=dict(row); r["best_instant_utc"]=instant.strftime("%Y-%m-%d %H:%M"); r["best_date"]=day.isoformat(); r["iso"]=iso_label(day); out.append(r)
    return out
def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:raise RuntimeError(f"No visibility rows generated for {path.name}")
    ending = "\r\n" if path.exists() and b"\r\n" in path.read_bytes() else "\n"
    with path.open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator=ending); w.writeheader(); w.writerows(rows)
def display_bayer(r):
    bayer=r.get("bayer","").strip()
    if bayer in GREEK_BAYER:
        con=r.get("con","").strip(); return f"{GREEK_BAYER[bayer]} {con}" if con else GREEK_BAYER[bayer]
    return bayer
def in_milky_way(r):
    key=display_bayer(r); entry=REGION_OBJECTS.get("bayer",{}).get(key,{}); return bool(entry.get("milky_way",{}).get("inside",False))
def star_event(r,fixed_id_override=None):
    proper=r.get("proper","").strip(); bayer=display_bayer(r); base=f"{proper} ({bayer})" if proper and bayer else (proper or bayer or f"{r.get('con','').strip()} star"); source_mag=(r.get("representative_vmax") or r.get("catalog_v") or r.get("mag") or "").strip(); aid=observing_aid_for_magnitude(source_mag); catalog_id=(r.get("hyg_id") or r.get("hip") or r.get("hd") or bayer or "").strip(); record=AlmanackObject(label=base,object_type="fixed_star",dec_deg=r["dec_deg"],best_date=dt.date.fromisoformat(r["best_date"]),observing_aid=aid,magnitude=source_mag,magnitude_display="whole",catalog_id=catalog_id,provenance=(r.get("brightness_basis") or "").strip(),variability_type=variable_type_for_row(r)); label=render_html(record)+(" — in the Milky Way" if in_milky_way(r) else ""); identifiers=[("hip",(r.get("hip") or "").strip()),("hd",(r.get("hd") or "").strip()),("bayer",bayer)]
    if fixed_id_override is not None:return CalendarEvent(label,int(fixed_id_override),aid.value if aid else None)
    for namespace,value in identifiers:
        if not value:continue
        fixed_id=FIXED_OBJECT_IDS.get((namespace.strip().lower(),value.strip().lower()))
        if fixed_id is not None:return CalendarEvent(label,fixed_id,aid.value if aid else None)
    attempted=", ".join(f"{namespace}:{value}" for namespace,value in identifiers if value) or "none"; raise RuntimeError(f"Permanent fixed-object identity not found for Calendar fixed star {base}; tried {attempted}")
def _messier_catalog_rows_for_annual_use():
    data=yaml.safe_load(FIXED_OBJECTS.read_text(encoding="utf-8")) or {}; fields=(data.get("schema") or {}).get("messier") or []; return [dict(zip(fields,row)) for row in data.get("messier") or []]

def page_date_map(year):
    ensure_coverage(year-1); ensure_coverage(year); occurrences=occurrences_for_iso_year(year); bayer_rows=read_csv("expanded-bayer-visibility-2026.csv"); bright_rows=read_csv("bright-star-visibility-2026.csv"); bayer_by_key={f"{row.get('bayer','').strip()}:{row.get('con','').strip()}":row for row in bayer_rows}; bright_by_key={}
    for row in bright_rows:
        if row.get("new_non_alpha_beta","").lower()!="yes":continue
        key=(row.get("proper") or "").strip() or f"{row.get('bayer','').strip()}:{row.get('con','').strip()}"; bright_by_key[key]=row
    additional = {source: {row[field]: row for row in read_csv(filename)}
                  for source, filename, field in ADDITIONAL_CATALOGS}
    events=defaultdict(list); generated={"expanded-bayer":[],"bright-star":[],"messier":[],
                                       **{source: [] for source in additional}}
    # Use the first existing source's occurrence for overlapping physical targets.
    # Keep every source occurrence in the cache for audit and catalog coverage.
    canonical_days = {}
    for occurrence in occurrences:
        if occurrence.get("fixed_object_id") is not None:
            day = dt.date.fromisoformat(occurrence["best_date"])
            # Distinct civil years can legitimately fall in one ISO year.
            canonical_days.setdefault((occurrence["fixed_object_id"], day.year), day)
    for occurrence in sorted(occurrences,key=lambda item:item["best_jd_tdb"]):
        source=occurrence["source"]; key=occurrence["key"]; day=dt.date.fromisoformat(occurrence["best_date"])
        if occurrence.get("fixed_object_id") is not None:
            day = canonical_days[(occurrence["fixed_object_id"], day.year)]
        if source=="expanded-bayer":
            row=dict(bayer_by_key[key]); row["best_instant_utc"]=occurrence["best_utc"].replace("Z","")[:16]; row["best_date"]=occurrence["best_date"]; row["iso"]=occurrence["iso"]; generated["expanded-bayer"].append(row); events[day].append(star_event(row,occurrence["fixed_object_id"]))
        elif source=="bright-star":
            row=dict(bright_by_key[key]); row["best_instant_utc"]=occurrence["best_utc"].replace("Z","")[:16]; row["best_date"]=occurrence["best_date"]; row["iso"]=occurrence["iso"]; generated["bright-star"].append(row); events[day].append(star_event(row,occurrence["fixed_object_id"]))
        elif source=="messier":
            identity=key.strip(); catalog=MESSIER_CATALOG.get(identity)
            if catalog is None:raise RuntimeError(f"Missing {identity} from {FIXED_OBJECTS.name} Messier catalog")
            if catalog.get("dec_deg") is None:raise RuntimeError(f"Missing declination for {identity} in {FIXED_OBJECTS.name}")
            generated["messier"].append({**dict(catalog),"best_instant_utc":occurrence["best_utc"].replace("Z","")[:16],"best_date":occurrence["best_date"],"iso":occurrence["iso"]})
            messier_mag=str(catalog.get("mag") or "").strip()
            fixed_id=(int(occurrence["fixed_object_id"]) if occurrence.get("fixed_object_id") is not None else None); target_key=None if fixed_id is not None else f"messier:{identity}"; events[day].append(CalendarEvent(render_html(AlmanackObject(label=identity,object_type="deep_sky",dec_deg=catalog["dec_deg"],best_date=day,observing_aid=ObservingAid.TELESCOPE,magnitude=messier_mag,magnitude_display="whole")),fixed_id,ObservingAid.TELESCOPE.value,target_key))
        elif source in additional:
            row = dict(additional[source][key])
            row.update(best_instant_utc=occurrence["best_utc"].replace("Z", "").replace("T", " ")[:16],
                       best_date=day.isoformat(), iso=iso_label(day))
            generated[source].append(row)
            events[day].append(catalog_event(source, row, day, occurrence.get("fixed_object_id")))
        else:raise RuntimeError(f"Unknown annual fixed-sky source: {source}")
    if not occurrences:raise RuntimeError(f"No annual fixed-sky records found for ISO {year}")
    for source, rows in generated.items():
        filename = source.replace("_", "-")
        write_csv(SRC/"generated"/f"{filename}-visibility-{year}.csv", rows)
    return {day: merge_same_targets(values) for day, values in events.items()}

def pages_for_events(root,events):
    pages=[]
    for iso_year in sorted({d.isocalendar().year for d in events}):pages.extend(weekly_pages(iso_year))
    return pages
def _event_identity(value):
    base=value.split(" — ",1)[0]; return re.sub(r"\s+"," ",re.sub(r"<[^>]+>","",base)).strip().lower()
def inject(root,year,events):
    changed=0
    for page in pages_for_events(root,events):
        original=page.read_text(encoding="utf-8"); text=ensure_calendar_metadata(original,page)
        for d,vals in events.items():
            keep=get_event_records(text,d)
            if keep is None:continue
            ids={v.fixed_object_id for v in vals if v.fixed_object_id is not None}
            keys={v.catalog_target_key for v in vals if v.catalog_target_key is not None}
            labels={_event_identity(v.html) for v in vals}
            keep=[x for x in keep if x.fixed_object_id not in ids
                  and x.catalog_target_key not in keys and _event_identity(x.html) not in labels]
            records=merge_same_targets(keep+list(vals)); text,found=set_events(text,d,records)
            if not found:raise RuntimeError(f"Could not update {d} in {page}")
        if text!=original:page.write_text(text,encoding="utf-8"); changed+=1
    return changed
def main():
    for year in requested_years():
        events=page_date_map(year); c2=inject(PUBLIC,year,events); print(f"{year}: canonical fixed-sky entries with observing glyph, declination band, season and Milky Way membership; updated {c2} public pages")
if __name__=="__main__":main()
