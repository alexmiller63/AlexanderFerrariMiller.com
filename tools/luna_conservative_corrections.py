#!/usr/bin/env python3
"""Correct narrowly verified stellar-class errors in generated review drafts.

This edits only generated review copies, never recovered originals or live stories.
It does not approve publication. Every replacement is reported.
"""
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"generated/luna-editorial"

def main():
    queue=json.loads((BASE/"review-queue.json").read_text(encoding="utf-8"))["stories"]
    comparisons={str(x["task_id"]):x for x in json.loads((BASE/"distance-spectral-check.json").read_text(encoding="utf-8"))["stories"]}
    output=[]
    for item in queue:
        key=str(item["task_id"])
        path=ROOT/item["prepared_path"]
        old=path.read_text(encoding="utf-8")
        row=comparisons[key]
        spec=row.get("catalogue_spectral_type") or ""
        expected=re.match(r"\s*([OBAFGKM])\d",spec,re.I)
        replacements=[]
        updated=old
        if expected:
            correct=expected.group(1).upper()
            mismatches={f["stated"] for f in row["flags"] if f["type"]=="spectral_class_discrepancy"}
            for wrong in sorted(mismatches):
                # Correct only literal letter-class labels; avoid automatically
                # rewriting color, temperature, age, luminosity or spectral subtype.
                pat=re.compile(r"\b"+re.escape(wrong)+r"([- ])type\b",re.I)
                updated,n=pat.subn(lambda m:correct+m.group(1)+"type",updated)
                if n:
                    replacements.append({"from":wrong+"-type","to":correct+"-type","count":n,
                                         "evidence":"SIMBAD spectral type "+spec})
        if updated!=old:
            path.write_text(updated,encoding="utf-8")
        output.append({"task_id":key,"title":item["title"],"review_draft":item["prepared_path"],
                       "changes":replacements,"remaining_review":"Check contextual descriptions and all other scientific claims",
                       "research_checked":False,"finder_checked":False,"publication_checked":False})
    report={"total":len(output),"stories_edited":sum(bool(x["changes"]) for x in output),
            "publication_approved":0,"paid_api_calls":0,"stories":output}
    (BASE/"conservative-corrections.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("Conservative review-draft corrections:",report["stories_edited"],"stories")
    for item in output:
        if item["changes"]:
            print(item["task_id"],item["title"],item["changes"])

if __name__=="__main__":
    main()
