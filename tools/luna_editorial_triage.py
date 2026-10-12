#!/usr/bin/env python3
"""Unattended, read-only editorial triage for all recovered Luna stories.

This is a screening pass, not scientific verification or editorial approval.
It never calls paid APIs, rewrites originals, or publishes drafts.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "research/luna-pilot-recovered/38194839310"
OUTPUT = ROOT / "generated/luna-editorial-triage.json"

def inspect(task):
    key = str(task["id"])
    manuscript = SOURCE / f"{key}.md"
    gate_file = SOURCE / f"{key}.gate.json"
    audit_file = SOURCE / f"{key}.audit.txt"
    research_file = SOURCE / f"{key}.research.txt"
    record = {"task_id": key, "title": task["title"], "status": "blocked",
              "needs_independent_source_review": True, "publication_approved": False,
              "issues": []}
    missing = [p.name for p in (manuscript, gate_file, audit_file, research_file) if not p.is_file()]
    if missing:
        record["issues"].append("Missing: " + ", ".join(missing))
        return record
    raw = manuscript.read_text(encoding="utf-8")
    gate = json.loads(gate_file.read_text(encoding="utf-8").rstrip().removesuffix("\\n"))
    audit = audit_file.read_text(encoding="utf-8").strip()
    if not re.search(r"(?m)^#\s+\S", raw):
        record["issues"].append("Publisher-compatible Markdown H1 missing")
    if not re.search(r"(?m)^Dek:\s*\S", raw):
        record["issues"].append("Pilot Dek missing")
    if not re.search(r"https?://\S+", raw):
        record["issues"].append("No source URL in manuscript")
    if not gate.get("screen_passed", False):
        record["issues"].append("Original pilot structural gate failed")
    if not audit:
        record["issues"].append("Empty editorial audit")
    if not gate.get("publication_approved", False):
        record["issues"].append("Independent editorial approval not recorded")
    record["manuscript_words"] = len(raw.split())
    record["original_gate_checks"] = gate.get("checks", {})
    record["audit_excerpt"] = audit[:900]
    record["status"] = "needs_editorial_review"
    return record

def main():
    tasks = json.loads((ROOT / "research/luna-pilot-candidates.json").read_text(encoding="utf-8"))
    records = [inspect(task) for task in tasks]
    report = {"schema_version": 1, "total": len(records),
              "screened": sum(x["status"] == "needs_editorial_review" for x in records),
              "blocked": sum(x["status"] == "blocked" for x in records),
              "published": 0, "paid_api_calls": 0,
              "limitations": "Automated triage does not verify science, sources, or finder geometry.",
              "stories": records}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "stories"}, indent=2))
    for r in records:
        print(f"{r['task_id']}: {r['title']} — {r['status']} ({len(r['issues'])} issues)")
    if len(records) != 10 or report["blocked"]:
        raise SystemExit("Some recovered story files are missing")

if __name__ == "__main__":
    main()
