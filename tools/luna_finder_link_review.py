#!/usr/bin/env python3
"""Check prepared story targets and canonical reader links without publishing.

This validates link construction and catalogue identity, not whether a finder
image is scientifically correct or deployed for every future week.
"""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from fixed_object_stories import COLLECTIONS, reader_story_url, story_path

BASE=ROOT/"generated/luna-editorial"
def main():
    entries=json.loads((BASE/"review-queue.json").read_text(encoding="utf-8"))["stories"]
    objects={str(x["fixed_object_id"]):x for x in json.loads((ROOT/"database/fixed-objects.json").read_text(encoding="utf-8"))["fixed_objects"]}
    output=[]
    for item in entries:
        obj_id=str(item["fixed_object_id"])
        candidate=Path(item["prepared_path"])
        collection=candidate.parent.name
        canonical=story_path(collection,int(obj_id)) if collection in COLLECTIONS else None
        issues=[]
        if not canonical:
            issues.append("Unsupported collection")
        elif candidate.name!=canonical.name:
            issues.append("Story filename differs from canonical fixed object ID")
        if obj_id not in objects:
            issues.append("Missing permanent catalogue object")
        if not (ROOT/candidate).is_file():
            issues.append("Missing prepared draft")
        public=f"/stories/{collection}/{obj_id}.html"
        try:
            reader=reader_story_url(public)
        except ValueError as exc:
            issues.append(str(exc))
            reader=None
        output.append({"task_id":item["task_id"],"title":item["title"],"fixed_object_id":obj_id,
                       "public_story_url":public,"weekly_page_relative_url":reader,
                       "link_structure_valid":not issues,"issues":issues,
                       "finder_scientifically_checked":False,"finder_checked":False,
                       "publication_approved":False})
    report={"total":len(output),"link_structure_valid":sum(x["link_structure_valid"] for x in output),
            "finder_checked":0,"publication_approved":0,"stories":output}
    (BASE/"finder-link-review.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("Canonical story link structure valid:",report["link_structure_valid"],"/",report["total"])
    for row in output:
        print(row["task_id"],row["title"],"OK" if row["link_structure_valid"] else row["issues"])

if __name__=="__main__":
    main()
