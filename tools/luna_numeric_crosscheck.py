#!/usr/bin/env python3
"""Automatically cross-check manuscript numeric claims against SIMBAD fields.

Only explicit SIMBAD 'Distance' and 'Flux V' fields are candidates. A mismatch
is a review flag, not automatic correction or publication approval.
"""
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"generated/luna-editorial"
def main():
    claims=json.loads((BASE/"claim-review.json").read_text(encoding="utf-8"))["stories"]
    sources={str(x["task_id"]):x for x in json.loads((BASE/"source-evidence/index.json").read_text(encoding="utf-8"))["stories"]}
    result=[]
    for story in claims:
        key=str(story["task_id"])
        src=sources[key]
        raw=(ROOT/src["evidence_file"]).read_text(encoding="utf-8") if src.get("evidence_file") else ""
        # SIMBAD plain-text output can vary by object and database version.
        flux=re.search(r"(?im)^\s*Flux\s+V\s*:\s*([+-]?\d+(?:\.\d+)?)",raw)
        v=float(flux.group(1)) if flux else None
        flags=[]
        for claim in story["claims"]:
            sentence=claim["text"]
            if "brightness" not in claim["topics"]:
                continue
            # Compare only explicitly identified visual magnitudes, never a
            # generic magnitude that may refer to another band or epoch.
            m=re.search(r"(?i)\b(?:visual|V.band|V\s+band)\s+magnitude\s+(?:of\s+|is\s+|about\s+|approximately\s+)?([+-]?\d+(?:\.\d+)?)",sentence)
            if m and v is not None:
                stated=float(m.group(1))
                if abs(stated-v)>0.35:
                    flags.append({"claim":sentence[:500],"type":"visual_magnitude_discrepancy",
                                  "stated":stated,"simbad_flux_v":v,"difference":round(abs(stated-v),3),
                                  "action":"Verify band, variability and epoch before editing"})
        result.append({"task_id":key,"title":story["title"],"simbad_flux_v":v,
                       "numeric_flags":flags,"flag_count":len(flags),
                       "publication_approved":False})
    report={"total":len(result),"numeric_discrepancies":sum(x["flag_count"] for x in result),
            "claims_verified":0,"publication_approved":0,"paid_api_calls":0,"stories":result}
    (BASE/"numeric-crosscheck.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("SIMBAD visual magnitude numeric discrepancies:",report["numeric_discrepancies"])
    for x in result:
        print(x["task_id"],x["title"],"V:",x["simbad_flux_v"],"flags:",x["flag_count"])

if __name__=="__main__":
    main()
