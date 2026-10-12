#!/usr/bin/env python3
"""Render missing pilot finders using the established fixed-object geometry renderer."""
import json
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import populate_fixed_object_artwork_by_date as artwork
import populate_sky_notes_artwork_by_date as legacy
def main():
    catalog=Path(sys.argv[1])
    if not catalog.is_file():
        raise SystemExit("Pinned HYG catalogue unavailable")
    queue=json.loads((ROOT/"generated/luna-editorial/review-queue.json").read_text())["stories"]
    registry=json.loads(legacy.GEOMETRY_REGISTRY.read_text(encoding="utf-8"))
    by_hip=legacy.fixed_object_id_by_hip()
    metadata,_=legacy.fixed_object_metadata()
    results=[]
    for item in queue:
        fid=int(item["fixed_object_id"])
        target=ROOT/"sky-notes-artwork"/"objects"/str(fid)/"finder.svg"
        specpath=ROOT/"sky-notes-artwork"/"specs"/"objects"/f"{fid}.json"
        if target.is_file():
            results.append({"id":fid,"result":"already_exists"})
            continue
        try:
            task={"fixed_object_id":fid,"name":item["title"],"type":"star"}
            spec=artwork.make_spec(task,registry,by_hip,metadata)
            specpath.parent.mkdir(parents=True,exist_ok=True)
            specpath.write_text(json.dumps(spec,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
            target.parent.mkdir(parents=True,exist_ok=True)
            subprocess.run([sys.executable,str(ROOT/"tools/render_sky_note_finder.py"),
                            str(catalog),str(specpath),str(target)],check=True)
            results.append({"id":fid,"result":"rendered"})
        except Exception as exc:
            results.append({"id":fid,"result":"blocked","error":str(exc)})
            print(f"Finder {fid}: {exc}",file=sys.stderr)
    out=ROOT/"generated/luna-editorial/finder-generation.json"
    out.write_text(json.dumps({"stories":results},indent=2)+"\n",encoding="utf-8")
    print(json.dumps(results,indent=2))
    if any(x["result"]=="blocked" for x in results):
        raise SystemExit("One or more finders could not be rendered")
if __name__=="__main__":
    main()
