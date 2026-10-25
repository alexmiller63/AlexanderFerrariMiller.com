#!/usr/bin/env python3
"""Conservative, read-only Pilot publication audit. No writing or publishing."""
from pathlib import Path
import json
import re
from collections import defaultdict

root = Path("generated/luna-pilot")
if not root.is_dir():
    raise SystemExit("Missing generated/luna-pilot")
groups = defaultdict(list)
for p in root.rglob("*.md"):
    if re.fullmatch(r"[0-9]+\.md", p.name):
        groups[p.stem].append(p)

rows = []
for ident, paths in sorted(groups.items(), key=lambda item: int(item[0])):
    for p in sorted(paths):
        stem = p.with_suffix("")
        checks = {}
        checks["nonempty"] = bool(p.read_text(encoding="utf-8").strip())
        checks["evidence_exists"] = p.with_suffix(".evidence.json").is_file()
        checks["gate_exists"] = p.with_suffix(".gate.json").is_file()
        checks["audit_exists"] = p.with_suffix(".audit.txt").is_file()
        gate = {}
        if checks["gate_exists"]:
            try:
                gate = json.loads(p.with_suffix(".gate.json").read_text(encoding="utf-8"))
                checks["gate_parseable"] = isinstance(gate, dict)
            except (ValueError, UnicodeError):
                checks["gate_parseable"] = False
        else:
            checks["gate_parseable"] = False
        # Unknown gate schema cannot establish passing quality checks.
        status = "blocked" if not checks["nonempty"] or checks["gate_parseable"] is False else "needs_review"
        rows.append({"id": ident, "path": str(p), "status": status, "checks": checks,
                     "gate": gate if isinstance(gate, dict) else {}})
report = {"total_files": len(rows), "unique_ids": len(groups),
          "duplicate_ids": {k: [str(p) for p in v] for k,v in groups.items() if len(v)>1},
          "status_counts": {s: sum(r["status"]==s for r in rows) for s in ("ready_to_publish","needs_review","blocked")},
          "note": "Conservative triage: no story is marked ready until the gate schema and publication requirements are explicitly verified.",
          "stories": rows}
Path("pilot-publication-audit.json").write_text(json.dumps(report, indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k not in ("stories","duplicate_ids")},indent=2))
