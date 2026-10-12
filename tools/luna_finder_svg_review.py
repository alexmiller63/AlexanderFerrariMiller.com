#!/usr/bin/env python3
"""Check actual finder SVGs for each editorial object, without false approval."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"generated/luna-editorial"
def main():
    entries=json.loads((BASE/"review-queue.json").read_text(encoding="utf-8"))["stories"]
    result=[]
    for entry in entries:
        obj_id=int(entry["fixed_object_id"])
        finder=ROOT/"sky-notes-artwork"/"objects"/str(obj_id)/"finder.svg"
        issues=[]
        if not finder.is_file():
            issues.append("Finder SVG missing from checkout")
        else:
            try:
                tree=ET.parse(finder)
                if not tree.getroot().tag.endswith("svg"):
                    issues.append("Finder file is not SVG")
                if finder.stat().st_size<300:
                    issues.append("Finder SVG unusually small")
            except ET.ParseError as exc:
                issues.append("Invalid SVG XML: "+str(exc))
        result.append({"task_id":entry["task_id"],"title":entry["title"],"fixed_object_id":obj_id,
                       "finder_path":str(finder.relative_to(ROOT)),"svg_structurally_valid":not issues,
                       "issues":issues,"finder_checked":False,
                       "scientific_geometry_verified":False,"publication_approved":False})
    report={"total":len(result),"svg_structurally_valid":sum(x["svg_structurally_valid"] for x in result),
            "scientific_geometry_verified":0,"publication_approved":0,"stories":result}
    (BASE/"finder-svg-review.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("Finder SVG structure valid:",report["svg_structurally_valid"],"/",report["total"])
    for item in result:
        print(item["task_id"],item["title"],"OK" if item["svg_structurally_valid"] else item["issues"])
if __name__=="__main__":
    main()
