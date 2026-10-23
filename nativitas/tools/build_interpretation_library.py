#!/usr/bin/env python3
"""Build a deterministic, reusable Nativitas interpretation library.

This tool compiles existing editorial content; it does not fabricate or
independently verify historical astrological interpretations.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLANETS = ["sun","moon","mercury","venus","mars","jupiter","saturn","uranus","neptune","pluto"]
SIGNS = ["aries","taurus","gemini","cancer","leo","virgo","libra","scorpio","sagittarius","capricorn","aquarius","pisces"]
APPROVED = {"approved", "reviewed-against-online-reference"}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="nativitas-library")
    p.add_argument("--batch-size", type=int, default=20)
    args = p.parse_args()
    if args.batch_size < 1:
        p.error("batch-size must be positive")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    aspect_data = json.loads((ROOT/"data/aspect-interpretations.json").read_text())
    placement_path = ROOT/"data/placement-interpretations.json"
    if placement_path.exists():
        placement_data = json.loads(placement_path.read_text())
    else:
        placement_data = {"entries": []}
    placements = {(e["planet"], e["sign"]): e for e in placement_data["entries"]}
    if len(placements) != len(placement_data["entries"]):
        raise ValueError("Duplicate placement entries")
    expected = {(p,s) for p in PLANETS for s in SIGNS}
    if set(placements) - expected:
        raise ValueError("Unexpected placement entries")
    aspect_entries = aspect_data["entries"]
    approved_aspects = [e for e in aspect_entries if e.get("status") in APPROVED and e.get("sources") and e.get("text","").strip()]
    approved_placements = [e for e in placement_data["entries"] if e.get("status") in APPROVED and e.get("sources") and e.get("text","").strip()]
    pending = [{"type":"placement","planet":p,"sign":s} for p,s in sorted(expected-set(placements))]
    pending += [{"type":"placement", "planet":e["planet"], "sign":e["sign"]} for e in placement_data["entries"] if e not in approved_placements]
    pending += [{"type":"aspect","pair":e["pair"],"aspect":e["aspect"]} for e in aspect_entries if e.get("status") != "astronomically-unavailable" and e not in approved_aspects]
    library = {"schema_version":1,"scope":"modern Western tropical natal astrology","scientific_status":"Astrological interpretations are not scientifically validated.","placements":approved_placements,"aspects":approved_aspects}
    (out/"library.json").write_text(json.dumps(library,indent=2,ensure_ascii=False)+"\n")
    (out/"review-queue.json").write_text(json.dumps(pending[:args.batch_size],indent=2)+"\n")
    report = {"placement_slots":120,"approved_placements":len(approved_placements),"approved_aspects":len(approved_aspects),"pending_review":len(pending),"batch_size":args.batch_size}
    (out/"progress.json").write_text(json.dumps(report,indent=2)+"\n")
    print("[NATIVITAS] Reusable library compiled; no unreviewed interpretations published.",flush=True)
    for key,value in report.items():
        print(f"{key}: {value}",flush=True)
    print("Review queue exported; generation of source-grounded prose requires editorial work.",flush=True)

if __name__ == "__main__":
    main()
