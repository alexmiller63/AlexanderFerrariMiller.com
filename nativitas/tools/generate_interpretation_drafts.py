#!/usr/bin/env python3
"""Checkpointed Nativitas catalog builder. Does not claim source verification."""
import argparse,datetime,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PLANETS={"sun":"identity and purpose","moon":"emotion and habit","mercury":"thinking and communication","venus":"affection and values","mars":"action and conflict","jupiter":"growth and belief","saturn":"discipline and limitation","uranus":"change and independence","neptune":"imagination and uncertainty","pluto":"power and transformation"}
SIGNS={"aries":"initiative and directness","taurus":"stability and persistence","gemini":"curiosity and exchange","cancer":"care and belonging","leo":"creative self-expression","virgo":"analysis and service","libra":"balance and partnership","scorpio":"intensity and depth","sagittarius":"exploration and philosophy","capricorn":"responsibility and ambition","aquarius":"independence and collective concerns","pisces":"imagination and receptivity"}
APPROVED={"approved","reviewed-against-online-reference"}
def save(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix(".tmp")
 tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 tmp.replace(path)
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("--batch-size",type=int,default=20)
 args=parser.parse_args()
 if args.batch_size<1: parser.error("batch size must be positive")
 placements_path=ROOT/"data/placement-interpretations.json"
 aspects_path=ROOT/"data/aspect-interpretations.json"
 progress_path=ROOT/"generation-progress.json"
 placements=json.loads(placements_path.read_text()) if placements_path.exists() else {"schema_version":1,"entries":[]}
 aspects=json.loads(aspects_path.read_text())
 existing={(e["planet"],e["sign"]) for e in placements["entries"]}
 if len(existing)!=len(placements["entries"]): raise ValueError("Duplicate placement entry")
 todo=[(p,s) for p in PLANETS for s in SIGNS if (p,s) not in existing]
 if len(aspects["entries"])!=225: raise ValueError("Expected 225 aspect slots")
 def report(status,current=None):
  approved_placements=sum(e.get("status") in APPROVED and e.get("sources") for e in placements["entries"])
  approved_aspects=sum(e.get("status") in APPROVED and e.get("sources") for e in aspects["entries"])
  excluded=sum(e.get("status")=="astronomically-unavailable" for e in aspects["entries"])
  filled=len(placements["entries"])+len(aspects["entries"])
  review_pending=filled-approved_placements-approved_aspects-excluded
  state={"status":status,"total":345,"cataloged":filled,"remaining_uncataloged":345-filled,"approved":approved_placements+approved_aspects,"excluded":excluded,"awaiting_review":review_pending,"current":current,"updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"note":"Drafts are unverified. Approved counts reflect catalog status, not independent source verification."}
  save(progress_path,state)
  print("[PROGRESS]",json.dumps(state),flush=True)
 report("running")
 for p,s in todo[:args.batch_size]:
  text=f"In modern Western tropical astrology, {p.title()} is associated with {PLANETS[p]}. {s.title()} is traditionally associated with {SIGNS[s]}. This pairing is an editorial outline awaiting verification against specific references."
  placements["entries"].append({"planet":p,"sign":s,"text":text,"status":"draft-awaiting-source-verification","sources":[],"tradition":"modern-western-tropical"})
  save(placements_path,placements)
  report("running",f"{p.title()} in {s.title()}")
 report("complete" if len(placements["entries"])==120 else "batch-complete")
if __name__=="__main__": main()
