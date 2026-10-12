#!/usr/bin/env python3
"""Read-only bridge audit for Luna pilot drafts and permanent Star Almanack IDs.

Pilot task IDs are not permanent fixed-object IDs. Never grant review approval,
overwrite manuscripts, or publish unverified paid drafts automatically.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    tasks = json.loads((ROOT / "research/luna-pilot-candidates.json").read_text())
    objects = json.loads((ROOT / "database/fixed-objects.json").read_text())["fixed_objects"]
    report = []
    for task in tasks:
        match = re.search(r"HIP\s+(\d+)", task.get("facts", ""))
        hip = match.group(1) if match else None
        matches = [obj for obj in objects if hip and any(
            re.search(r"\bHIP\s+" + re.escape(hip) + r"\b", str(source.get("source_key", "")))
            for source in obj.get("source_records", []))]
        draft = ROOT / "generated/luna-pilot" / (str(task["id"]) + ".md")
        report.append({
            "pilot_task_id": str(task["id"]), "title": task["title"], "hip": hip,
            "permanent_ids": [obj["fixed_object_id"] for obj in matches],
            "draft_saved": draft.is_file(), "identity_resolved": len(matches) == 1,
            "publication_ready": False,
            "reason": "Independent research, finder and publication reviews required."
        })
    target = ROOT / "generated/luna-publication-bridge.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"stories": report, "paid_api_calls": 0,
        "automatic_publication": False}, indent=2) + "\n", encoding="utf-8")
    print(target.read_text(encoding="utf-8"))
    if any(not item["identity_resolved"] for item in report):
        raise SystemExit("Unresolved catalogue identity; no publication attempted")

if __name__ == "__main__":
    main()
