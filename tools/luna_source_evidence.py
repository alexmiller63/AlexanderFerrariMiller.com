#!/usr/bin/env python3
"""Fetch primary catalogue evidence for each Luna manuscript, without paid APIs.

Each star is independent. Network failures are recorded and never treated as
successful source verification. This is evidence gathering, not editorial signoff.
"""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "generated/luna-editorial/review-queue.json"
DEST = ROOT / "generated/luna-editorial/source-evidence"

def main():
    entries = json.loads(QUEUE.read_text(encoding="utf-8"))["stories"]
    DEST.mkdir(parents=True, exist_ok=True)
    results = []
    for entry in entries:
        hip = next((part.split("HIP%20", 1)[1].split("&", 1)[0] for part in entry["source_urls"]
                    if "HIP%20" in part), None)
        record = {"task_id": entry["task_id"], "title": entry["title"], "hip": hip,
                  "source": "SIMBAD CDS astronomical database",
                  "verified": False, "publication_approved": False}
        if hip is None or not hip.isdigit():
            record["status"] = "blocked_missing_hip"
        else:
            url = "https://simbad.cds.unistra.fr/simbad/sim-id?Ident=HIP%20" + hip + "&output.format=ASCII"
            record["url"] = url
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "StarAlmanackEditorialEvidence/1.0"})
                with urllib.request.urlopen(request, timeout=18) as response:
                    payload = response.read(180000).decode("utf-8", errors="replace")
                if len(payload.strip()) < 100 or "Identifier not found" in payload:
                    raise ValueError("Catalogue response absent or not useful")
                evidence = DEST / (entry["task_id"] + "-simbad.txt")
                evidence.write_text(payload, encoding="utf-8")
                record["status"] = "source_retrieved_unverified"
                record["evidence_file"] = str(evidence.relative_to(ROOT))
                record["bytes"] = len(payload.encode("utf-8"))
            except (OSError, ValueError) as exc:
                record["status"] = "source_unavailable"
                record["error"] = str(exc)[:250]
        results.append(record)
        time.sleep(0.3)
    report = {"total": len(results), "retrieved": sum(r["status"] == "source_retrieved_unverified" for r in results),
              "publication_approved": 0, "paid_api_calls": 0, "stories": results}
    (DEST / "index.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "stories"}, indent=2))
    for record in results:
        print(record["task_id"], record["title"], record["status"])

if __name__ == "__main__":
    main()
