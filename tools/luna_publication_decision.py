#!/usr/bin/env python3
"""Single end-to-end editorial decision report for the ten paid pilot drafts.

No publication unless scientific, finder and editorial approvals are real.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"generated/luna-editorial"
def load(name):
    return json.loads((BASE/name).read_text(encoding="utf-8"))
def main():
    queue=load("review-queue.json")["stories"]
    narrative={str(x["task_id"]):x for x in load("narrative-review.json")["stories"]}
    charts={str(x["task_id"]):x for x in load("finder-svg-review.json")["stories"]}
    corrections={str(x["task_id"]):x for x in load("conservative-corrections.json")["stories"]}
    numeric={str(x["task_id"]):x for x in load("numeric-crosscheck.json")["stories"]}
    rows=[]
    for story in queue:
        key=str(story["task_id"])
        blockers=[]
        if narrative[key]["hold_count"]:
            blockers.append(str(narrative[key]["hold_count"])+" scientific/contextual passages need independent review")
        if not charts[key]["svg_structurally_valid"]:
            blockers.append("Finder SVG missing or malformed")
        if not charts[key]["scientific_geometry_verified"]:
            blockers.append("Finder geometry not independently verified")
        if numeric[key]["flag_count"]:
            blockers.append("Numeric claims require review")
        if corrections[key]["changes"]:
            blockers.append("Review surrounding prose after automated spectral correction")
        approvals_path = ROOT / "research/luna-publication-approvals.json"
        approvals = json.loads(approvals_path.read_text(encoding="utf-8")) if approvals_path.exists() else {}
        approval = approvals.get(key, {})
        if approval.get("editor_approved") is not True:
            blockers.append("Publication editor approval not recorded")
        if approval.get("scientific_approved") is not True:
            blockers.append("Independent scientific approval not recorded")
        if approval.get("finder_approved") is not True:
            blockers.append("Independent finder approval not recorded")
        rows.append({"task_id":key,"title":story["title"],"blockers":blockers,
                     "approved":not blockers,"published":False})
    summary={"total":len(rows),"ready_to_publish":sum(not row["blockers"] for row in rows),"published":0,
             "missing_or_invalid_finders":sum(not charts[str(x["task_id"])]["svg_structurally_valid"] for x in queue),
             "contextual_review_passages":sum(narrative[str(x["task_id"])]["hold_count"] for x in queue),
             "paid_api_calls":0,"stories":rows}
    (BASE/"publication-decision.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print("END-TO-END PUBLICATION DECISION")
    print("Prepared:",summary["total"],"Published:",summary["published"],
          "Missing/invalid finder files:",summary["missing_or_invalid_finders"],
          "Contextual review passages:",summary["contextual_review_passages"])
    for row in rows:
        print(row["task_id"],row["title"],"BLOCKED:", "; ".join(row["blockers"]))
if __name__=="__main__":
    main()
