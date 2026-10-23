#!/usr/bin/env python3
"""Resumable draft generation with public progress. Drafts are NOT source-verified."""
import argparse,json,time,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PLANETS={"sun":"identity and purpose","moon":"emotion and habit","mercury":"thinking and communication","venus":"affection and values","mars":"action and conflict","jupiter":"growth and belief","saturn":"discipline and limitation","uranus":"change and independence","neptune":"imagination and uncertainty","pluto":"power and transformation"}
SIGNS={"aries":"initiative and directness","taurus":"stability and persistence","gemini":"curiosity and exchange","cancer":"care and belonging","leo":"creative self-expression","virgo":"analysis and service","libra":"balance and partnership","scorpio":"intensity and depth","sagittarius":"exploration and philosophy","capricorn":"responsibility and ambition","aquarius":"independence and collective concerns","pisces":"imagination and receptivity"}
def save(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix(".tmp")
 temp.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n")
 temp.replace(path)
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--batch-size",type=int,default=20)
 args=ap.parse_args()
 if args.batch_size<1: ap.error("batch-size must be positive")
 dest=ROOT/"data/placement-interpretations.json"
 data=json.loads(dest.read_text()) if dest.exists() else {"schema_version":1,"entries":[]}
 existing={(x["planet"],x["sign"]) for x in data["entries"]}
 pending=[(p,s) for p in PLANETS for s in SIGNS if (p,s) not in existing]
 progress=ROOT/"generation-progress.json"
 start=time.time()
 def report(status,current=None):
  completed=120-len(pending)
  save(progress,{"status":status,"completed":completed,"total":120,"remaining":len(pending),"current":current,"updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"note":"Automated drafts are unverified editorial starting points; not approved interpretations."})
  print(f"[PROGRESS] {completed}/120 {status} {current or ''}",flush=True)
 report("running")
 for p,s in pending[:args.batch_size]:
  text=f"In modern Western tropical astrology, {p.title()} is associated with {PLANETS[p]}. {s.title()} is traditionally associated with {SIGNS[s]}. Their combination is conventionally read through these themes; this draft requires source-specific editorial review."
  data["entries"].append({"planet":p,"sign":s,"text":text,"status":"draft-awaiting-source-verification","sources":[],"tradition":"modern-western-tropical"})
  existing.add((p,s))
  pending.remove((p,s))
  save(dest,data)
  report("running",f"{p.title()} in {s.title()}")
 report("complete" if not pending else "batch-complete")
if __name__=="__main__": main()
