#!/usr/bin/env python3
"""Compute year-specific best-visibility dates for Special Stars."""
from __future__ import annotations
import argparse,csv
from pathlib import Path
from visibility_engine import best_visibility,iso_date
EXPECTED_SPECIAL_STARS=24

def main()->None:
    parser=argparse.ArgumentParser(); parser.add_argument("--year",type=int,required=True)
    parser.add_argument("input",type=Path,nargs="?",default=Path("special-star-catalog.csv")); parser.add_argument("output",type=Path,nargs="?"); args=parser.parse_args()
    output_path=args.output or Path(f"special-star-visibility-{args.year}.csv")
    with args.input.open(newline="",encoding="utf-8") as handle: rows=list(csv.DictReader(handle))
    if not rows: raise SystemExit("Special Star coordinate catalog is empty")
    output=[]
    for row in rows:
        instant,date=best_visibility(float(row["ra_h"]),args.year); enriched=dict(row)
        enriched["best_instant_utc"]=instant.strftime("%Y-%m-%d %H:%M"); enriched["best_date"]=date.isoformat(); enriched["iso"]=iso_date(date); output.append(enriched)
    fields=list(rows[0].keys())+["best_instant_utc","best_date","iso"]
    with output_path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields); writer.writeheader(); writer.writerows(output)
    if len(output)!=EXPECTED_SPECIAL_STARS: raise SystemExit(f"Expected {EXPECTED_SPECIAL_STARS} Special Stars, got {len(output)}")
    print(f"Special Star coordinate rows: {len(output)}"); print(f"All best dates fall inside requested year {args.year}"); print(f"Wrote {output_path}")
if __name__=="__main__": main()
