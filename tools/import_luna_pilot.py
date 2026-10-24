#!/usr/bin/env python3
"""Import the ten recovered Luna pilot drafts without losing or prematurely publishing work.

Drafts remain pending until a human-reviewed story receives all three attestations.
Run again safely: existing manuscript files are NEVER overwritten.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "research/luna-pilot-recovered/38194839310"
STORIES = ROOT / "stories"
# Pilot sequence numbers are not permanent star IDs.
PILOT = {
    1: ("alpha-stars", "HIP 677"),
    2: ("beta-stars", "HIP 746"),
    3: ("special-stars", "HIP 1067"),
    4: ("alpha-stars", "HIP 3179"),
    5: ("special-stars", "HIP 4427"),
    6: ("special-stars", "HIP 6686"),
    7: ("special-stars", "HIP 8886"),
    8: ("special-stars", "HIP 11484"),
    9: ("alpha-stars", "HIP 11767"),
    10: ("special-stars", "HIP 12706"),
}
# The category for a pilot is checked against the catalogue below, not blindly trusted.
BAYER = {"Gamma Pegasi": ("Gam", "Peg"), "Alpha Cassiopeiae": ("Alp", "Cas"),
         "Gamma Cassiopeiae": ("Gam", "Cas"), "Alpha Ursae Minoris": ("Alp", "UMi"),
         "Gamma Ceti": ("Gam", "Cet")}

def resolve(catalogue, key):
    matches = []
    for obj in catalogue["fixed_objects"]:
        records = obj.get("source_records") or []
        if key.startswith("HIP "):
            match = any(str(r.get("source_key", "")).strip() == key or
                        re.search(r"(?<!\d)" + re.escape(key) + r"(?!\d)", str(r.get("source_key", "")))
                        for r in records)
        else:
            code, constellation = BAYER[key]
            match = any(
                (r.get("source") == "fixed-objects.yaml:bayer") and
                (re.search(r"(?:^|;)\s*bayer_code=" + re.escape(code) + r"(?:;|$)",
                           str((r.get("facts") or {}).get("notes", ""))) is not None) and
                str((r.get("facts") or {}).get("constellation", "")).strip().lower() in
                {constellation.lower(), key.split(" ", 1)[1].lower()}
                for r in records
            )
        if match:
            matches.append(obj["fixed_object_id"])
    if len(matches) != 1:
        raise ValueError(f"{key}: expected exactly one catalogue match, got {matches}")
    return matches[0]

def parse_pilot(text):
    lines = text.strip().splitlines()
    barrier = next((i for i, line in enumerate(lines) if line.strip() == "---"), None)
    if barrier is None:
        title = next((s.strip(" *") for s in lines if s.strip()), "")
        body = "\n".join(lines[1:]).strip()
        if not title or not body:
            raise ValueError("draft missing title or body")
        return title, "Recovered Luna pilot manuscript; editorial review required.", body
    header, body = "\n".join(lines[:barrier]), "\n".join(lines[barrier + 1:]).strip()
    if not body:
        raise ValueError("empty draft body")
    hed = re.search(r"(?im)^\*{0,2}(?:Hed:|\*\*Hed:\*\*)\s*(.+)$", header)
    dek = re.search(r"(?im)^\*{0,2}(?:Dek:|Dec:|\*\*Dek:\*\*|\*\*Dec:\*\*)\s*(.+)$", header)
    if hed:
        title = hed.group(1).strip(" *") or next((s.strip(" *") for s in header.splitlines()[1:] if s.strip()), "")
    else:
        title = next((s.strip(" *") for s in header.splitlines() if s.strip()), "")
    if dek:
        description = dek.group(1).strip(" *") or next((s.strip(" *") for s in header.splitlines()[header[:dek.start()].count("\n")+1:] if s.strip()), "")
    else:
        description = "Recovered Luna pilot manuscript; editorial review required."
    if not title:
        raise ValueError("missing title")
    return title, description, body

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Create only absent pending manuscripts")
    args = parser.parse_args()
    catalog = json.loads((ROOT / "database/fixed-objects.json").read_text(encoding="utf-8"))
    results = []
    seen = set()
    errors = []
    for number, (collection, key) in PILOT.items():
        try:
            path = SOURCE / f"{number}.md"
            if not path.is_file():
                raise ValueError(f"missing pilot source {path}")
            object_id = resolve(catalog, key)
            if object_id in seen:
                raise ValueError(f"duplicate permanent ID {object_id}")
            seen.add(object_id)
            target = STORIES / collection / f"{object_id}.md"
            if target.exists():
                state = "PRESERVED existing file"
            elif args.write:
                hed, dek, body = parse_pilot(path.read_text(encoding="utf-8"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    f"---\nfixed_object_id: {object_id}\nstatus: pending\n"
                    "research_checked: false\nfinder_checked: false\n"
                    "publication_checked: false\n---\n"
                    f"# {hed}\n\n{dek}\n\n{body}\n", encoding="utf-8"
                )
                state = "CREATED pending draft"
            else:
                state = "WOULD CREATE pending draft"
            results.append(dict(pilot=number, object_id=object_id, path=str(target.relative_to(ROOT)), state=state))
        except Exception as exc:
            errors.append(f"Pilot {number}: {exc}")
    print(json.dumps(dict(results=results, errors=errors), indent=2))
    if errors:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
