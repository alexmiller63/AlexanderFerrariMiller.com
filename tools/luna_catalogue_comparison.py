#!/usr/bin/env python3
"""Conservative unattended identity comparison against retrieved SIMBAD evidence.

No inference from missing fields; no approval or publication from this check.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "generated/luna-editorial"
def main():
    evidence = json.loads((BASE / "source-evidence/index.json").read_text(encoding="utf-8"))["stories"]
    queue = {str(x["task_id"]): x for x in json.loads((BASE / "review-queue.json").read_text(encoding="utf-8"))["stories"]}
    output = []
    for item in evidence:
        key = str(item["task_id"])
        expected = item.get("hip")
        q = queue[key]
        record = {"task_id": key, "title": q["title"], "hip": expected,
                  "identity_consistent": False, "research_checked": False,
                  "publication_approved": False, "issues": []}
        source_path = ROOT / item["evidence_file"] if item.get("evidence_file") else None
        manuscript_path = ROOT / q["prepared_path"] if q.get("prepared_path") else None
        if not source_path or not source_path.exists():
            record["issues"].append("SIMBAD evidence missing")
        elif not expected or not re.search(r"(?i)\bHIP\s*"+re.escape(expected)+r"\b", source_path.read_text(encoding="utf-8")):
            record["issues"].append("SIMBAD response does not visibly confirm expected HIP identifier")
        if not manuscript_path or not manuscript_path.exists():
            record["issues"].append("Prepared manuscript missing")
        # HIP is an internal cross-reference; published prose need not mention it.
        # The catalogue evidence confirms the identifier independently of prose.
        record["identity_consistent"] = not record["issues"]
        record["next_action"] = "Independent review of distance, spectral type, magnitude, variable behavior, and observing advice"
        output.append(record)
    report = {"total": len(output), "identity_consistent": sum(x["identity_consistent"] for x in output),
              "needs_attention": sum(not x["identity_consistent"] for x in output),
              "publication_approved": 0, "paid_api_calls": 0, "stories": output}
    (BASE / "catalogue-comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="stories"}, indent=2))
    for item in output:
        print(item["task_id"], item["title"], "IDENTITY OK" if item["identity_consistent"] else "REVIEW REQUIRED", "; ".join(item["issues"]))

if __name__ == "__main__":
    main()
