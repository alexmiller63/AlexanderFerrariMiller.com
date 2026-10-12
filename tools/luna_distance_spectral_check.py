#!/usr/bin/env python3
"""Flag possible distance and spectral-class errors using SIMBAD evidence.

Conservative triage only: source metadata and prose can differ by epoch,
measurement method or system component. Never grant publication approval.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "generated/luna-editorial"
CLASSES = "OBAFGKM"
LY_PER_PC = 3.261563777

def catalogue(raw):
    spectral = re.search(r"(?im)^\s*Spectral\s+(?:type|classification)\s*:\s*([^\r\n]+)", raw)
    parallax = re.search(r"(?im)^\s*Parallax\s*:\s*([+-]?\d+(?:\.\d+)?)", raw)
    return (spectral.group(1).strip() if spectral else None,
            float(parallax.group(1)) if parallax else None)

def main():
    queue = json.loads((BASE / "review-queue.json").read_text(encoding="utf-8"))["stories"]
    evidence = {str(x["task_id"]): x for x in json.loads((BASE / "source-evidence/index.json").read_text(encoding="utf-8"))["stories"]}
    report = []
    for entry in queue:
        key = str(entry["task_id"])
        src = evidence[key]
        raw = (ROOT / src["evidence_file"]).read_text(encoding="utf-8") if src.get("evidence_file") else ""
        spec, parallax = catalogue(raw)
        text = (ROOT / entry["prepared_path"]).read_text(encoding="utf-8")
        flags = []
        catalogue_class = re.search(r"\b([" + CLASSES + r"])\s*\d", spec or "", re.I)
        if not catalogue_class and spec:
            catalogue_class = re.search(r"\b([" + CLASSES + r"])\b", spec, re.I)
        reference_class = catalogue_class.group(1).upper() if catalogue_class else None
        for m in re.finditer(r"\b([" + CLASSES + r"])[- ]type\b", text, re.I):
            stated = m.group(1).upper()
            if reference_class and stated != reference_class:
                flags.append({"type": "spectral_class_discrepancy", "stated": stated,
                              "catalogue": reference_class, "context": text[max(0,m.start()-65):m.end()+100],
                              "action": "Check classification and component identity before correcting"})
        for m in re.finditer(r"(?i)\b(?:about|approximately|roughly|nearly|around)?\s*(\d+(?:\.\d+)?)\s*light[- ]years?\b", text):
            stated = float(m.group(1))
            if parallax and parallax > 0:
                estimate = 1000 / parallax * LY_PER_PC
                if abs(stated-estimate)/estimate > .25:
                    flags.append({"type": "distance_discrepancy", "stated_ly": stated,
                                  "parallax_estimate_ly": round(estimate, 2),
                                  "context": text[max(0,m.start()-65):m.end()+80],
                                  "action": "Review parallax uncertainties, multiple systems, and distance estimates"})
        report.append({"task_id": key, "title": entry["title"],
                       "catalogue_spectral_type": spec, "catalogue_parallax_mas": parallax,
                       "flags": flags, "flag_count": len(flags), "publication_approved": False})
    output = {"total": len(report), "flagged": sum(x["flag_count"] for x in report),
              "approved": 0, "paid_api_calls": 0, "stories": report}
    (BASE / "distance-spectral-check.json").write_text(json.dumps(output, indent=2)+"\n", encoding="utf-8")
    print("Distance/spectral review flags:", output["flagged"])
    for row in report:
        print(row["task_id"], row["title"], "spectral:", row["catalogue_spectral_type"],
              "parallax:", row["catalogue_parallax_mas"], "flags:", row["flag_count"])
        for flag in row["flags"][:8]:
            print("  ", flag["type"], flag.get("stated", flag.get("stated_ly")),
                  "vs", flag.get("catalogue", flag.get("parallax_estimate_ly")))

if __name__ == "__main__":
    main()
