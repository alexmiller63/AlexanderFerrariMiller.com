#!/usr/bin/env python3
"""Verify generated constellation-center events survived the full Almanack pipeline."""
from __future__ import annotations
import argparse,csv,datetime as dt
from pathlib import Path
from almanack_calendar import ensure_calendar_metadata,get_events
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/"Star-Almanack-Repo"; GENERATED=SRC/"generated"; ROOTS=(SRC/"site",ROOT/"almanack")
def parse_years():
 p=argparse.ArgumentParser(description="Verify Star Almanack constellation centers"); p.add_argument("years",metavar="YEAR",type=int,nargs="+"); a=p.parse_args(); years=list(dict.fromkeys(a.years))
 for y in years:
  if not 1900<=y<=2100:p.error(f"YEAR must be between 1900 and 2100: {y}")
 return years
def read_rows(year):
 path=GENERATED/f"constellation-observance-{year}.csv"
 if not path.exists():raise SystemExit(f"Missing generated constellation table: {path}")
 with path.open(newline="",encoding="utf-8") as h:rows=list(csv.DictReader(h))
 if not rows:raise SystemExit(f"{path}: no constellation-center rows")
 return rows
def page_for_date(root,day):
 iso=day.isocalendar(); return root/str(iso.year)/f"W{iso.week:02d}"/"index.html"
def verify_root(root,rows,year):
 for row in rows:
  name=row["name"].strip(); day=dt.date.fromisoformat(row["center_best_date"]); page=page_for_date(root,day)
  if not page.exists():raise SystemExit(f"{year}: missing weekly page for {name}: {page}")
  text=ensure_calendar_metadata(page.read_text(encoding="utf-8"),page); cell=get_events(text,day)
  if cell is None:raise SystemExit(f"{year}: missing canonical calendar row for {name} on {day} in {page}")
  items=cell.split("<br>") if cell not in ("","—") else []; prefix=f"{name} center — Constellation — "; count=sum(item.startswith(prefix) for item in items)
  if count!=1:raise SystemExit(f"{year}: expected {name} center exactly once on {day} in {page}, found {count}")
def main():
 years=parse_years()
 for year in years:
  rows=read_rows(year)
  for root in ROOTS:verify_root(root,rows,year)
  print(f"{year}: constellation-center survival PASS — {len(rows)}/{len(rows)} source + {len(rows)}/{len(rows)} public")
 print(f"Constellation-center final-output regression PASS for: {' '.join(map(str,years))}")
if __name__=="__main__":main()
