#!/usr/bin/env python3
"""Flag scientific narrative that cannot be validated by a spectral-letter edit.

This is an editorial hold list. It never treats keyword matches as proof.
"""
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"generated/luna-editorial"
RULES={
 "stellar_color":r"\b(?:orange|yellow|blue.white|reddish|red hue|white hue|color|colour)\b",
 "emission_and_disk":r"\b(?:emission lines?|circumstellar|gaseous disk|Be star|Balmer|hydrogen alpha)\b",
 "stellar_evolution":r"\b(?:supernovae?|gamma.ray bursts?|stellar winds?|mass loss|evolv|critical velocity)\b",
 "observing_conditions":r"\b(?:overhead|winter months?|autumn|best time|northern hemisphere|southern hemisphere)\b",
 "system_properties":r"\b(?:binary|companion|pulsat|variable|rotation|metallic|chemically peculiar)\b",
}
def main():
    entries=json.loads((BASE/"review-queue.json").read_text(encoding="utf-8"))["stories"]
    out=[]
    for e in entries:
        path=ROOT/e["prepared_path"]
        prose=path.read_text(encoding="utf-8")
        lines=prose.splitlines()
        holds=[]
        for n,line in enumerate(lines,1):
            tags=[name for name,pat in RULES.items() if re.search(pat,line,re.I)]
            if tags:
                holds.append({"line":n,"topics":tags,"excerpt":line[:500],
                              "reason":"Needs contextual scientific review beyond a catalogue identity or spectral letter check"})
        out.append({"task_id":e["task_id"],"title":e["title"],"holds":holds,
                    "hold_count":len(holds),"editorial_approved":False})
    report={"stories":out,"total":len(out),"holds":sum(x["hold_count"] for x in out),
            "publication_approved":0,"paid_api_calls":0}
    (BASE/"narrative-review.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("Narrative contextual review flags:",report["holds"])
    for row in out:
        print(row["task_id"],row["title"],row["hold_count"],"context flags")

if __name__=="__main__":
    main()
