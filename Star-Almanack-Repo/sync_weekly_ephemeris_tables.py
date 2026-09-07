#!/usr/bin/env python3
"""Synchronize Almanack week sections from weekly-ephemeris-2026.csv."""
from __future__ import annotations
import csv, re, sys
from datetime import date
from pathlib import Path
ROOT = Path(__file__).parent
EPHEMERIS = ROOT / "weekly-ephemeris-2026.csv"
PRIMARY = [("☉ Sun","sun"),("☽ Moon","moon"),("☿ Mercury","mercury"),("♀ Venus","venus"),("♂ Mars","mars"),("♃ Jupiter","jupiter"),("♄ Saturn","saturn")]
EXTENDED = [("♅ Uranus","uranus"),("♆ Neptune","neptune"),("⚳ Ceres","ceres"),("♇ Pluto","pluto")]

def value(row, key):
    b = row.get(key + "_beta", "").strip()
    return row[key] + (f"<br><small>{b}</small>" if b else "")

def table(columns, row):
    return "| " + " | ".join(label for label,_ in columns) + " |\n" + "|" + "|".join("---:" for _ in columns) + "|\n" + "| " + " | ".join(value(row,key) for _,key in columns) + " |"

def replacement(row):
    monday=date.fromisoformat(row["monday_utc"])
    return "### Weekly Solar-System Ephemeris\n\n" + f"**Snapshot:** Monday, {monday:%b} {monday.day}, {monday.year} · 00:00 UTC\n\n" + table(PRIMARY,row) + "\n\n**Extended targets:**\n\n" + table(EXTENDED,row) + "\n\n**β** = ecliptic latitude (+ north, − south).\n\n"

def main():
    target=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"almanack.md"
    with EPHEMERIS.open(encoding="utf-8",newline="") as f: rows={r["iso_week"]:r for r in csv.DictReader(f)}
    if len(rows)!=53: raise SystemExit(f"Expected 53 ephemeris rows, found {len(rows)}")
    for key,row in rows.items():
        for required in ("uranus","neptune","ceres","pluto"):
            if not row.get(required): raise SystemExit(f"{key} is missing {required}")
    text=target.read_text(encoding="utf-8").replace("53 weekly classical-planet snapshots","53 weekly Solar-System snapshots")
    weeks=[int(x) for x in re.findall(r"(?m)^## ISO 2026-W(\d{2})\s*$",text)]
    if not weeks: raise SystemExit(f"No ISO 2026 week sections found in {target}")
    for week in weeks:
        key=f"2026-W{week:02d}"
        rx=re.compile(rf"(?ms)(^## ISO {re.escape(key)}\s*$.*?)(^### Weekly (?:Classical-Planet|Solar-System) Ephemeris\s*$.*?)(?=^### Sky Note\s*$)")
        m=rx.search(text)
        if not m: raise SystemExit(f"Could not locate ephemeris section for {key} in {target}")
        text=text[:m.start()]+m.group(1)+replacement(rows[key])+text[m.end():]
    target.write_text(text,encoding="utf-8")
    print(f"Synchronized {len(weeks)} weekly Solar-System ephemeris sections in {target}")
if __name__=="__main__": main()
