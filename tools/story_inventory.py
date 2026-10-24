#!/usr/bin/env python3
"""Read-only inventory of saved story manuscripts by permanent object ID."""
import json
import re
from pathlib import Path
from import_luna_pilot import PILOT, resolve

ROOT = Path(__file__).resolve().parents[1]
catalogue = json.loads((ROOT / "database/fixed-objects.json").read_text(encoding="utf-8"))
catalogue_ids = {int(o["fixed_object_id"]) for o in catalogue["fixed_objects"]}
collections = ("alpha-stars", "beta-stars", "special-stars", "messier", "caldwell", "finest")
main = {int(p.stem): str(p.relative_to(ROOT))
        for folder in collections for p in (ROOT / "stories" / folder).glob("*.md")
        if p.stem.isdigit()}
generated = {int(p.stem): str(p.relative_to(ROOT))
             for p in (ROOT / "generated/luna-pilot").glob("*.md") if p.stem.isdigit()}
pilot = {}
pilot_errors = []
for number, (_, key) in PILOT.items():
    source = ROOT / "research/luna-pilot-recovered/38194839310" / f"{number}.md"
    if not source.exists():
        pilot_errors.append(f"Missing pilot source {number}")
        continue
    try:
        permanent_id = int(resolve(catalogue, key))
        if permanent_id in pilot:
            pilot_errors.append(f"Pilot collision on permanent ID {permanent_id}")
        pilot[permanent_id] = str(source.relative_to(ROOT))
    except Exception as exc:
        pilot_errors.append(f"Pilot {number}: {exc}")
saved = set(main) | set(generated) | set(pilot)
unrecognized = sorted(saved - catalogue_ids)
missing = sorted(catalogue_ids - saved)
report = {
    "scope": "Entire fixed-object registry; not necessarily the curated ~531 story targets",
    "registry_objects": len(catalogue_ids),
    "main_story_files": len(main),
    "generated_luna_drafts": len(generated),
    "recovered_pilot_permanent_ids": len(pilot),
    "unique_saved_permanent_ids": len(saved),
    "overlaps": {
        "main_and_generated": sorted(set(main) & set(generated)),
        "main_and_pilot": sorted(set(main) & set(pilot)),
        "generated_and_pilot": sorted(set(generated) & set(pilot)),
    },
    "missing_registry_ids": missing,
    "missing_registry_count": len(missing),
    "saved_ids_not_in_registry": unrecognized,
    "pilot_errors": pilot_errors,
    "saved_id_sources": {
        str(i): {"main": main.get(i), "generated": generated.get(i), "pilot": pilot.get(i)}
        for i in sorted(saved)
    },
}
out = ROOT / "generated/story-inventory.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k not in ("missing_registry_ids", "saved_id_sources")}, indent=2))
print("Wrote", out)
if pilot_errors or unrecognized:
    raise SystemExit("Inventory contains identity errors; paid generation must not start")
