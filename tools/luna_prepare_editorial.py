#!/usr/bin/env python3
"""Prepare all recovered paid drafts as non-publishing, reviewable story files.

Never invent approvals, alter originals, or spend API funds. Outputs are CI
artifacts for editorial revision and review, not published pages.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from luna_publication_bridge import ROOT as BRIDGE_ROOT

def main():
    tasks = json.loads((ROOT / "research/luna-pilot-candidates.json").read_text())
    objects = json.loads((ROOT / "database/fixed-objects.json").read_text())["fixed_objects"]
    destination = ROOT / "generated/luna-editorial/stories"
    status = []
    for task in tasks:
        hip = re.search(r"HIP\s+(\d+)", task["facts"]).group(1)
        matches = [o for o in objects if any(
            re.search(r"\bHIP\s+" + hip + r"\b", str(s.get("source_key", "")))
            for s in o.get("source_records", []))]
        if len(matches) != 1:
            status.append({"task_id": task["id"], "status": "blocked_identity"})
            continue
        permanent_id = matches[0]["fixed_object_id"]
        src = ROOT / "research/luna-pilot-recovered/38194839310" / (task["id"] + ".md")
        if not src.exists():
            status.append({"task_id": task["id"], "status": "blocked_missing_draft"})
            continue
        raw = src.read_text(encoding="utf-8")
        hed = re.search(r"(?m)^Hed:\s*(.+)$", raw)
        dek = re.search(r"(?m)^Dek:\s*(.+)$", raw)
        fallback_dek = "An editorial draft about " + task["title"] + "; its scientific claims await independent review."
        dek_text = dek.group(1).strip() if dek else fallback_dek
        title = hed.group(1).strip() if hed else raw.splitlines()[0].strip()
        if not title:
            title = task["title"]
        body = re.sub(r"(?m)^Hed:.*\n|^Dek:.*\n", "", raw).strip()
        body = re.sub(r"^---\s*", "", body).strip()
        collection = "alpha-stars" if task["title"] in ("Alpheratz", "Schedar", "Polaris") else "beta-stars" if task["title"] == "Caph" else "special-stars"
        target = destination / collection / (str(permanent_id) + ".md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "---\nfixed_object_id: " + str(permanent_id) +
            "\nstatus: pending\nresearch_checked: false\nfinder_checked: false\npublication_checked: false\n---\n\n# " +
            title + "\n\n" + dek_text + "\n\n" + body + "\n",
            encoding="utf-8")
        status.append({"task_id": task["id"], "fixed_object_id": permanent_id,
                       "status": "prepared_pending_review", "path": str(target.relative_to(ROOT))})
    report = ROOT / "generated/luna-editorial/preparation-status.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"stories": status, "paid_api_calls": 0,
        "published": 0, "next_step": "Independent scientific/source/finder editorial review"}, indent=2) + "\n")
    print(report.read_text())
    if len(status) != 10 or any(x["status"] != "prepared_pending_review" for x in status):
        raise SystemExit("One or more drafts require recovery before editorial review")

if __name__ == "__main__":
    main()
