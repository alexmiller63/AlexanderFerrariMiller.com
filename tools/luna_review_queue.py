#!/usr/bin/env python3
"""Produce an unattended per-story editorial work queue with resumable evidence.

This report does not confer source verification or publishing approval.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / "generated/luna-editorial/preparation-status.json"
OUT = ROOT / "generated/luna-editorial/review-queue.json"

def main():
    prepared = json.loads(PREP.read_text(encoding="utf-8"))["stories"]
    tasks = {str(x["id"]): x for x in json.loads((ROOT / "research/luna-pilot-candidates.json").read_text(encoding="utf-8"))}
    queue = []
    for record in prepared:
        key = str(record["task_id"])
        task = tasks[key]
        src = ROOT / "research/luna-pilot-recovered/38194839310" / (key + ".md")
        audit = src.with_suffix(".audit.txt")
        research = src.with_suffix(".research.txt")
        status = record["status"]
        manuscript = src.read_text(encoding="utf-8") if src.exists() else ""
        queue.append({
            "task_id": key, "title": task["title"], "fixed_object_id": record.get("fixed_object_id"),
            "prepared_path": record.get("path"),
            "status": "awaiting_independent_verification" if status == "prepared_pending_review" else status,
            "source_urls": task.get("sources", []),
            "pilot_audit": audit.read_text(encoding="utf-8")[:12000] if audit.exists() else "",
            "pilot_research": research.read_text(encoding="utf-8")[:12000] if research.exists() else "",
            "claims_to_check": [s.strip() for s in re.split(r"(?<=[.!?])\s+", manuscript)
                                if re.search(r"\b(?:light.years?|spectral|magnitude|temperature|distance|variable|binary|giant|main.sequence)\b", s, re.I)][:30],
            "research_checked": False, "finder_checked": False, "publication_checked": False,
            "next_action": "Verify claims against authoritative sources, revise, check finder, and attest independently"
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"total": len(queue), "publication_approved": 0,
                               "paid_api_calls": 0, "stories": queue}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Editorial queue prepared:", len(queue), "stories")
    for x in queue:
        print(x["task_id"], x["title"], x["status"], "claims:", len(x["claims_to_check"]))
    if len(queue) != 10 or any(x["status"] != "awaiting_independent_verification" for x in queue):
        raise SystemExit("Incomplete preparation queue")

if __name__ == "__main__":
    main()
