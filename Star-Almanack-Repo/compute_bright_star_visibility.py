#!/usr/bin/env python3
"""Compute year-specific best-visibility dates for the bright-star layer."""
from __future__ import annotations
import argparse, csv, math
from pathlib import Path
from visibility_engine import best_visibility, iso_date

def magnitude_class(value: str) -> str:
    if not value: return ""
    return str(max(1, min(6, int(math.floor(float(value) + 0.5)))))

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("input", type=Path, nargs="?", default=Path("bright-stars-2mag.csv"))
    parser.add_argument("output", type=Path, nargs="?")
    args = parser.parse_args()
    output_path = args.output or Path(f"bright-star-visibility-{args.year}.csv")
    with args.input.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows: raise SystemExit("Bright-star catalog is empty")
    output=[]
    for row in rows:
        instant,date=best_visibility(float(row["ra_h"]), args.year)
        enriched=dict(row)
        enriched["best_instant_utc"]=instant.strftime("%Y-%m-%d %H:%M")
        enriched["best_date"]=date.isoformat(); enriched["iso"]=iso_date(date)
        enriched["mag_class"]=magnitude_class(row.get("representative_vmax", ""))
        enriched["new_non_alpha_beta"]="yes" if row.get("in_alpha_beta_layer")=="no" else "no"
        output.append(enriched)
    fields=list(rows[0].keys())+["best_instant_utc","best_date","iso","mag_class","new_non_alpha_beta"]
    with output_path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields); writer.writeheader(); writer.writerows(output)
    print(f"Dated bright-star systems: {len(output)}")
    print(f"Wrote {output_path}")
if __name__ == "__main__": main()
