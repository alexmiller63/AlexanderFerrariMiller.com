#!/usr/bin/env python3
"""Read-only, conservative story audit. Never grants editorial approval."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = ("alpha-stars", "beta-stars", "special-stars", "messier", "caldwell", "finest")
FIELDS = ("research_checked", "finder_checked", "publication_checked")

def audit_file(path):
    raw = path.read_text(encoding="utf-8")
    front = {}
    body = raw
    if raw.startswith("---\n"):
        parts = raw.split("---\n", 2)
        if len(parts) == 3:
            front = dict((k.strip(), v.strip().strip('"')) for k, v in
                         (line.split(":", 1) for line in parts[1].splitlines() if ":" in line))
            body = parts[2]
    parts = body.strip().split("\n\n", 2)
    narrative = parts[2] if len(parts) > 2 else ""
    words = len(narrative.split())
    urls = re.findall(r"https?://[^\s<>]+|doi:\s*10\.\S+", narrative, re.I)
    paragraphs = len([p for p in re.split(r"\n\s*\n", narrative) if p.strip()])
    issues = []
    expected = path.stem
    if front.get("fixed_object_id") != expected:
        issues.append("missing or mismatched permanent object ID")
    if not body.lstrip().startswith("# "):
        issues.append("missing Hed")
    if len(parts) < 3 or not parts[1].strip():
        issues.append("missing Dek")
    if words < 500:
        issues.append("body below 500 words")
    if paragraphs < 5:
        issues.append("fewer than five body paragraphs")
    if not urls:
        issues.append("no traceable URL or DOI in body")
    status = front.get("status", "pending")
    if status not in ("pending", "complete"):
        issues.append("invalid completion status")
    checks = {key: front.get(key) == "true" for key in FIELDS}
    if status == "complete" and (issues or not all(checks.values())):
        issues.append("marked complete without all required checks")
    return {"path": str(path.relative_to(ROOT)), "id": expected, "status": status,
            "body_words": words, "paragraphs": paragraphs, "citations": len(urls),
            "checks": checks, "structural_issues": issues,
            "automated_structure_pass": not issues,
            "editorial_approval_required": not checks["research_checked"],
            "finder_review_required": not checks["finder_checked"],
            "publication_review_required": not checks["publication_checked"]}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="generated/story-audit.json")
    p.add_argument("--strict", action="store_true", help="Fail on structural errors or invalid completion attestations")
    args = p.parse_args()
    paths = sorted(path for collection in COLLECTIONS
                   for path in (ROOT / "stories" / collection).glob("*.md"))
    records = [audit_file(path) for path in paths]
    summary = {"files": len(records),
               "complete": sum(r["status"] == "complete" and not r["structural_issues"] for r in records),
               "pending": sum(r["status"] != "complete" for r in records),
               "structural_failures": sum(bool(r["structural_issues"]) for r in records),
               "finder_checks_pending": sum(r["finder_review_required"] for r in records),
               "publication_checks_pending": sum(r["publication_review_required"] for r in records)}
    result = {"schema_version": 1, "scope": "all saved story files", "summary": summary,
              "limitations": ["URLs are extracted but not fetched", "Science is not fact-checked",
                              "Finder geometry and live publication are not tested",
                              "Completion attestations are read, never issued"], "stories": records}
    target = ROOT / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Audit report:", target)
    if args.strict and summary["structural_failures"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
