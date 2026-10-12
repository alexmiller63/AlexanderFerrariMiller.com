#!/usr/bin/env python3
"""Generate a per-claim editorial checklist from saved SIMBAD evidence.

This is an automated *screen*, not a scientific approval. It intentionally
never changes story text or the three publication gate flags.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "generated/luna-editorial"
TOPICS = {
    "distance": r"\b(?:light.years?|parsecs?|distance|parallax)\b",
    "classification": r"\b(?:spectral|main.sequence|giant|supergiant|dwarf|type [OBAFGKM])\b",
    "brightness": r"\b(?:magnitude|brightness|brightest|luminous|luminosity)\b",
    "variability": r"\b(?:variable|variability|pulsat|eclips|binary|companion)\b",
    "temperature": r"\b(?:temperature|kelvin|hotter|cooler)\b",
}
def main():
    queue = json.loads((BASE / "review-queue.json").read_text(encoding="utf-8"))["stories"]
    source = {str(x["task_id"]): x for x in json.loads((BASE / "source-evidence/index.json").read_text(encoding="utf-8"))["stories"]}
    out = []
    for entry in queue:
        key = str(entry["task_id"])
        draft = ROOT / entry["prepared_path"]
        manuscript = draft.read_text(encoding="utf-8")
        ev = source[key]
        evidence = (ROOT / ev["evidence_file"]).read_text(encoding="utf-8") if ev.get("evidence_file") else ""
        claims = []
        for sentence in re.split(r"(?<=[.!?])\s+", manuscript):
            categories = [name for name, pattern in TOPICS.items() if re.search(pattern, sentence, re.I)]
            if not categories:
                continue
            claims.append({"text": sentence.strip()[:700], "topics": categories,
                           "source_record_available": bool(evidence),
                           "verification_status": "requires_claim_level_review"})
        out.append({"task_id": key, "title": entry["title"], "claims": claims,
                    "claim_count": len(claims), "research_checked": False,
                    "publication_approved": False, "next_action": "Compare each claim to catalogue fields and external primary references"})
    report = {"stories": out, "total": len(out), "claims_flagged": sum(x["claim_count"] for x in out),
              "claims_verified": 0, "publication_approved": 0, "paid_api_calls": 0}
    (BASE / "claim-review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Scientific claims flagged:", report["claims_flagged"], "across", report["total"], "stories")
    for x in out:
        print(x["task_id"], x["title"], x["claim_count"], "claims pending")

if __name__ == "__main__":
    main()
