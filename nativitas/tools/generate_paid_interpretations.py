#!/usr/bin/env python3
"""Paid, resumable Nativitas editorial drafts. No automatic publication or source claims."""
import argparse, datetime, json, os, pathlib, urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
PLANETS="sun moon mercury venus mars jupiter saturn uranus neptune pluto".split()
SIGNS="aries taurus gemini cancer leo virgo libra scorpio sagittarius capricorn aquarius pisces".split()
ASPECTS="conjunction sextile square trine opposition".split()
KINDS=("natal-placement","natal-aspect","natal-planet-house","natal-house-sign","synastry-aspect","synastry-overlay")
# Conservative configurable upper-bound rates, USD per million tokens, for gpt-4.1-mini.
INPUT_RATE=0.40; OUTPUT_RATE=1.60
MAX_INPUT=2200; MAX_OUTPUT=400
def save(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix(".tmp");temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n");temp.replace(path)
def slots():
 for p in PLANETS:
  for s in SIGNS:yield ("natal-placement",p,s)
 for i,p in enumerate(PLANETS):
  for q in PLANETS[i+1:]:
   for a in ASPECTS:yield ("natal-aspect",p,q,a)
 for p in PLANETS:
  for h in range(1,13):yield ("natal-planet-house",p,str(h))
 for h in range(1,13):
  for s in SIGNS:yield ("natal-house-sign",str(h),s)
 for p in PLANETS:
  for q in PLANETS:
   for a in ASPECTS:yield ("synastry-aspect",p,q,a)
 for p in PLANETS:
  for h in range(1,13):yield ("synastry-overlay",p,str(h))
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--batch-size",type=int,default=25)
 ap.add_argument("--budget",type=float,default=1.0)
 ap.add_argument("--model",default="gpt-4.1-mini")
 args=ap.parse_args()
 if args.batch_size<1 or not 0<args.budget<=1:ap.error("batch size must be positive; budget must be between $0 and $1")
 if args.model!="gpt-4.1-mini":ap.error("Only the rate-checked gpt-4.1-mini model is supported")
 key=os.environ.get("OPENAI_API_KEY")
 if not key:raise SystemExit("OPENAI_API_KEY secret is required; no paid requests sent")
 path=DATA/"paid-interpretation-drafts.json";progress=ROOT/"paid-interpretation-progress.json"
 state=json.loads(path.read_text()) if path.exists() else {"schema_version":1,"entries":{},"spent_usd":0.0,"model":args.model}
 if state.get("model")!=args.model:raise SystemExit("Model mismatch")
 entries=state["entries"]
 # Cost reservations prevent starting a request whose worst-case configured cost exceeds budget.
 reserve=(MAX_INPUT*INPUT_RATE+MAX_OUTPUT*OUTPUT_RATE)/1000000
 all_slots=list(slots());pending=[x for x in all_slots if ":".join(x) not in entries]
 count=0;error=None
 try:
  for slot in pending[:args.batch_size]:
   if state["spent_usd"]+reserve>args.budget:break
   ident=":".join(slot)
   system=("Write one concise, specific, original interpretation (60-90 words) for a modern Western tropical astrology reference. "
           "Interpret symbolically, not as established science or deterministic prediction. "
           "Distinguish natal aspects from inter-person synastry. Avoid generic filler. "
           "Do not invent citations, quote books, or claim historical attribution. Return only the interpretation paragraph.")
   user="Interpretation ID: "+ident
   payload={"model":args.model,"messages":[{"role":"system","content":system},{"role":"user","content":user}],"max_tokens":MAX_OUTPUT,"temperature":0.4}
   request=urllib.request.Request("https://api.openai.com/v1/chat/completions",data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
   with urllib.request.urlopen(request,timeout=90) as response:result=json.load(response)
   usage=result.get("usage",{});ipt=usage.get("prompt_tokens",MAX_INPUT);opt=usage.get("completion_tokens",MAX_OUTPUT)
   # Reserve on abnormal usage; do not understate costs.
   charge=(max(ipt,0)*INPUT_RATE+max(opt,0)*OUTPUT_RATE)/1000000
   state["spent_usd"]+=charge
   content=result["choices"][0]["message"]["content"].strip()
   if not content:raise ValueError("Empty generated text")
   entries[ident]={"id":ident,"text":content,"status":"draft-awaiting-source-verification","sources":[],"model":args.model,"usage":{"input_tokens":ipt,"output_tokens":opt},"estimated_cost_usd":round(charge,8)}
   save(path,state);count+=1
   print(f"[{count}/{args.batch_size}] {ident} estimated cumulative spend ${state['spent_usd']:.4f}",flush=True)
 except Exception as exc:
  error=str(exc);print("Generation stopped:",error,flush=True)
 finally:
  save(path,state)
  save(progress,{"status":"error" if error else "batch-complete","generated_this_run":count,"total_slots":len(all_slots),"completed":len(entries),"remaining":len(all_slots)-len(entries),"estimated_spent_usd":round(state["spent_usd"],6),"budget_usd":args.budget,"model":args.model,"error":error,"updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"note":"Estimates use fixed model rates; drafts are unpublished and unverified. Budget is cumulative across runs."})
 if error:raise SystemExit(1)
if __name__=="__main__":main()
