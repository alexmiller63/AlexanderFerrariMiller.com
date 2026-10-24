#!/usr/bin/env python3
"""Select genuinely missing curated stories without paid API calls."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORY_DIRS = ("alpha-stars", "beta-stars", "special-stars", "messier", "caldwell", "finest")

def candidates(limit=10):
    objects = json.loads((ROOT / "database/fixed-objects.json").read_text())["fixed_objects"]
    existing = {int(p.stem) for folder in STORY_DIRS for p in (ROOT / "stories" / folder).glob("*.md") if p.stem.isdigit()}
    saved = ROOT / "generated/luna-pilot"
    # Any saved work or checkpoint reserves its permanent object ID.
    # Do not reselect interrupted research, evidence, audit or paid stages.
    if saved.exists():
        for p in saved.iterdir():
            if p.is_file():
                match = re.match(r"^(\d+)(?:\.|$)", p.name)
                if match:
                    existing.add(int(match.group(1)))
    existing.update(int(p.stem) for p in saved.glob("*.md") if p.stem.isdigit())
    # Do not repeat any previous pilot candidate until its status has been reconciled.
    previous = ROOT / "research/luna-pilot-candidates.json"
    if previous.exists():
        for task in json.loads(previous.read_text()):
            hip = re.search(r"Registry identity:\s*HIP\s+(\d+)", task.get("facts", ""))
            if hip:
                for obj in objects:
                    if any(re.search(r"\bHIP\s+" + hip.group(1) + r"\b", str(rec.get("source_key", "")), re.I) for rec in obj.get("source_records", [])):
                        existing.add(int(obj["fixed_object_id"]))
    selected = []
    for obj in sorted(objects, key=lambda o: int(o["fixed_object_id"])):
        ident = int(obj["fixed_object_id"])
        if ident in existing:
            continue
        hip = None
        name = None
        for record in obj.get("source_records", []):
            m = re.search(r"\bHIP\s+(\d+)\b", str(record.get("source_key", "")), re.I)
            if m:
                hip = m.group(1)
            facts = record.get("facts") or {}
            name = name or facts.get("name")
        if not hip or not name:
            continue
        selected.append({"id": str(ident), "title": str(name), "facts": "Registry identity: HIP " + hip + ". Source catalog identity only; all other claims require verification.", "sources": ["https://simbad.cds.unistra.fr/simbad/sim-id?Ident=HIP%20" + hip]})
        if len(selected) >= limit:
            break
    return selected

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", default="generated/luna-pilot-selected.json")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("limit must be 1..100")
    selected = candidates(args.limit)
    if not selected:
        raise SystemExit("No new eligible objects found; no paid calls allowed")
    path = ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(selected, indent=2) + "\n")
    print("NEW CANDIDATES:", len(selected))
    for item in selected:
        print(item["id"], item["title"])
