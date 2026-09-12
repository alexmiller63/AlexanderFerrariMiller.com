#!/usr/bin/env python3
"""Populate constellation-center events for requested Almanack years."""
from __future__ import annotations
import csv,datetime as dt,re,statistics,sys,unicodedata
from collections import defaultdict
from pathlib import Path
from almanack_calendar import ensure_calendar_metadata,get_events,set_events
from star_almanack_astronomy import best_visibility_occurrences_for_iso_year,declination_band,season_for
from star_almanack_objects import HTML_AID,observing_aid_for_magnitude
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/"Star-Almanack-Repo"; PUBLIC=ROOT/"almanack"; SOURCE_SITE=SRC/"site"; DEFAULT_YEARS=(2025,2026,2027)
CENTROID_SNAPSHOT=SRC/"constellation-observance-2026.csv"; BAYER_STARS=SRC/"expanded-bayer-stars.csv"; MARTZ_FIGURES=Path("/tmp/constellation_lines_iau.dat"); HYG_CATALOG=Path("/tmp/hygdata_v41.csv")
HYG_HIPPARCOS_SUPPLEMENTS={"55203":3.79}; FRONT_MATTER={"Men":{"rule":"alpha_beta_mean"},"Mic":{"rule":"alpha_beta_mean"},"Ser":{"rule":"martz_caput_cauda"}}
SERPENS_COMPONENTS=(
 {"name":"Serpens Caput","figure_part":"Caput","figure_key":"SerpensB","centroid_ra_h":"15.695035","centroid_dec_deg":"9.909187","sampled_area_sq_deg":"428.632","centroid_step_deg":"0.100"},
 {"name":"Serpens Cauda","figure_part":"Cauda","figure_key":"SerpensA","centroid_ra_h":"18.162525","centroid_dec_deg":"-6.367014","sampled_area_sq_deg":"208.365","centroid_step_deg":"0.100"},)
def requested_years():
 if len(sys.argv)==1:return DEFAULT_YEARS
 try:years=tuple(dict.fromkeys(int(x) for x in sys.argv[1:]))
 except ValueError as exc:raise SystemExit("Years must be integers, e.g. 2025 2026 2027") from exc
 if any(y<1 for y in years):raise SystemExit("Years must be positive integers")
 return years
def read_csv(path):
 with path.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def iso_label(d):y,w,wd=d.isocalendar(); return f"{y}-W{w:02d}-{wd}"
def normalize_name(value):
 text=unicodedata.normalize("NFKD",value); text="".join(ch for ch in text if not unicodedata.combining(ch)); return re.sub(r"[^a-z0-9]","",text.lower())
def alpha_beta_magnitudes():
 values=defaultdict(lambda:defaultdict(list))
 for row in read_csv(BAYER_STARS):
  con=(row.get("con") or "").strip(); greek=(row.get("greek") or "").strip(); raw=(row.get("mag") or "").strip()
  if not con or greek not in {"α","β"} or not raw:continue
  try:values[con][greek].append(float(raw))
  except ValueError:pass
 return values
def alpha_beta_mean(con,values):
 pair=values.get(con,{})
 if not pair.get("α") or not pair.get("β"):raise SystemExit(f"Front-matter alpha/beta rule cannot be resolved for {con}")
 return statistics.mean((min(pair["α"]),min(pair["β"])))
def read_hyg(path):
 if not path.is_file():raise SystemExit(f"Missing pinned HYG catalog: {path}")
 by_hip={}
 for row in read_csv(path):
  raw=(row.get("mag") or "").strip(); hip=(row.get("hip") or "").strip()
  if not raw or not hip:continue
  try:by_hip[str(int(float(hip)))]=float(raw)
  except ValueError:continue
 for hip,mag in HYG_HIPPARCOS_SUPPLEMENTS.items():by_hip.setdefault(hip,mag)
 return by_hip
def read_martz_figures(path):
 if not path.is_file():raise SystemExit(f"Missing pinned Martz/MacRobert figure data: {path}")
 figures={}; current=None
 for raw in path.read_text(encoding="utf-8").splitlines():
  line=raw.strip()
  if line.startswith("* "):current=line[2:].strip(); figures.setdefault(current,[]); continue
  if current is None or not line.startswith("["):continue
  for hip in re.findall(r'"(\d+)\*?"',line):
   if hip not in figures[current]:figures[current].append(hip)
 return figures
def median_figure_magnitude(key,figures,by_hip):
 hips=figures.get(key,[])
 if not hips:raise SystemExit(f"No member stars enumerated for adopted figure {key}")
 missing=[h for h in hips if h not in by_hip]
 if missing:raise SystemExit("Pinned HYG/Hipparcos magnitude set lacks V magnitudes for "+f"{key} member HIP(s): "+", ".join(missing))
 return statistics.median(by_hip[h] for h in hips)
def normal_figure_key(name,figures):
 wanted=normalize_name(name); matches=[k for k in figures if normalize_name(k)==wanted]
 if len(matches)!=1:raise SystemExit(f"Could not uniquely match {name} to adopted Martz/MacRobert figure data")
 return matches[0]
def constellation_magnitude(row,alpha_beta,figures,by_hip):
 con=row["abbr"].strip(); front=FRONT_MATTER.get(con)
 if front:
  rule=front["rule"]
  if rule=="alpha_beta_mean":return alpha_beta_mean(con,alpha_beta)
  if rule=="martz_caput_cauda":
   part=row.get("figure_part","").strip(); comp=next((x for x in SERPENS_COMPONENTS if x["figure_part"]==part),None)
   if comp is None:raise SystemExit(f"Serpens row lacks a recognized Caput/Cauda component: {part!r}")
   return median_figure_magnitude(comp["figure_key"],figures,by_hip)
  raise SystemExit(f"Unknown front-matter constellation rule for {con}: {rule}")
 return median_figure_magnitude(normal_figure_key(row["name"],figures),figures,by_hip)
def visibility_html(mag):
 aid=observing_aid_for_magnitude(str(mag))
 if aid is None:raise SystemExit(f"Could not derive observing aid for magnitude {mag}")
 return f'<span class="visibility-magnitude">{HTML_AID[aid]} V {mag:.1f}</span>'
def make_rows(source,iso_year):
 rows=[]
 for instant,day in best_visibility_occurrences_for_iso_year(float(source["centroid_ra_h"]),iso_year):
  rows.append({"name":source["name"],"abbr":source["abbr"],"figure_part":source.get("figure_part",""),"centroid_ra_h":source["centroid_ra_h"],"centroid_dec_deg":source["centroid_dec_deg"],"sampled_area_sq_deg":source["sampled_area_sq_deg"],"centroid_step_deg":source["centroid_step_deg"],"center_best_instant_utc":instant.strftime("%Y-%m-%d %H:%M"),"center_best_date":day.isoformat(),"center_iso":iso_label(day)})
 return rows
def source_rows():
 snaps=read_csv(CENTROID_SNAPSHOT)
 if len(snaps)!=88:raise SystemExit(f"Expected 88 centroid snapshot rows, got {len(snaps)}")
 sources=[]
 for snap in snaps:
  if snap["abbr"].strip()!="Ser":sources.append(snap)
  else:
   for comp in SERPENS_COMPONENTS:sources.append({**comp,"abbr":"Ser"})
 if len(sources)!=89:raise SystemExit(f"Expected 89 center identities after splitting Serpens, got {len(sources)}")
 return sources
def build_rows(year):
 rows=[]
 for source in source_rows():rows.extend(make_rows(source,year))
 if not rows:raise SystemExit(f"No constellation-center occurrences fall in ISO year {year}")
 for row in rows:
  if dt.date.fromisoformat(row["center_best_date"]).isocalendar().year!=year:raise SystemExit(f"Out-of-year constellation occurrence leaked into {year}: {row}")
 return rows
def write_csv(year,rows):
 out=SRC/"generated"/f"constellation-observance-{year}.csv"; out.parent.mkdir(parents=True,exist_ok=True)
 with out.open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def event_map(rows):
 events=defaultdict(list); alpha_beta=alpha_beta_magnitudes(); figures=read_martz_figures(MARTZ_FIGURES); by_hip=read_hyg(HYG_CATALOG)
 for row in rows:
  day=dt.date.fromisoformat(row["center_best_date"]); cls=f"{declination_band(row['centroid_dec_deg'])} {season_for(day)}"; mag=constellation_magnitude(row,alpha_beta,figures,by_hip); events[day].append(f"{row['name']} center — Constellation — {visibility_html(mag)} — {cls}")
 return events
BARE_LEGACY_STAR=re.compile(r'^✦ (?:α|β) star — .+$'); LEGACY_CENTER=re.compile(r'^(?:✦ )?.*? (?:geometric-center observance|center)(?: —)? .+$')
def clean_target_event_cell(cell):
 if cell in ("","—"):return []
 kept=[]
 for item in cell.split("<br>"):
  s=item.strip()
  if not s or BARE_LEGACY_STAR.match(s) or " — Constellation — " in s or "geometric-center observance" in s:continue
  if LEGACY_CENTER.match(s) and " — Asterism — " not in s:continue
  kept.append(item)
 return kept
def page_for_date(root,day):
 iso=day.isocalendar(); return root/str(iso.year)/f"W{iso.week:02d}"/"index.html"
def inject(root,events):
 changed=0; by_page=defaultdict(list)
 for day,vals in events.items():by_page[page_for_date(root,day)].append((day,vals))
 for page,dated in sorted(by_page.items(),key=lambda x:str(x[0])):
  if not page.exists():raise SystemExit(f"Missing weekly page for constellation event(s): {page}")
  original=page.read_text(encoding="utf-8"); text=ensure_calendar_metadata(original,page)
  for day,vals in dated:
   cell=get_events(text,day)
   if cell is None:raise SystemExit(f"Could not find canonical calendar row for {day} in {page}")
   keep=clean_target_event_cell(cell)
   for v in vals:
    if v not in keep:keep.append(v)
   text,found=set_events(text,day,"<br>".join(keep) if keep else "—")
   if not found:raise SystemExit(f"Could not update calendar row for {day} in {page}")
  if text!=original:page.write_text(text,encoding="utf-8"); changed+=1
 return changed
def validate(root,events):
 for day,vals in events.items():
  page=page_for_date(root,day)
  if not page.exists():raise SystemExit(f"Missing weekly page while validating constellation event(s): {page}")
  text=ensure_calendar_metadata(page.read_text(encoding="utf-8"),page); cell=get_events(text,day)
  if cell is None:raise SystemExit(f"Could not find canonical calendar row for {day} while validating {page}")
  items=cell.split("<br>") if cell not in ("","—") else []
  for value in vals:
   count=items.count(value)
   if count!=1:raise SystemExit(f"{root}: expected {value!r} exactly once on {day} in {page}, found {count}")
def main():
 for year in requested_years():
  rows=build_rows(year); write_csv(year,rows); events=event_map(rows); s=inject(SOURCE_SITE,events); p=inject(PUBLIC,events); validate(SOURCE_SITE,events); validate(PUBLIC,events); identities={(r["abbr"],r.get("figure_part","")) for r in rows}; print(f"{year}: {len(rows)} constellation-center ISO-year occurrence(s) across {len(identities)} represented identities; updated {s} source + {p} public pages")
if __name__=="__main__":main()
