#!/usr/bin/env python3
"""Draft reusable fixed-ID Sky Notes without scientific verification."""
import json, os, re, subprocess, time, urllib.request, urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"generated/sky-notes-2026-drafts"
BUDGET=float(os.environ.get('STORY_BUDGET_USD', '3.0'))
START_WEEK=int(os.environ.get('STORY_START_WEEK', '43'))
END_WEEK=int(os.environ.get('STORY_END_WEEK', '53'))
assert 1 <= START_WEEK <= END_WEEK <= 53
# Deliberately conservative reservation rates, not an OpenAI account billing cap.
MODEL=os.environ.get("STORY_MODEL") or os.environ.get("MODEL")
INPUT_RATE=float(os.environ.get("INPUT_PRICE", "2.0"))
OUTPUT_RATE=float(os.environ.get("OUTPUT_PRICE", "8.0"))
MAX_INPUT=3000
MAX_OUTPUT=900
RESERVE=(MAX_INPUT*INPUT_RATE+MAX_OUTPUT*OUTPUT_RATE)/1e6
def git(*args):
    return subprocess.run(["git",*args],cwd=ROOT,check=True,text=True,capture_output=True)
def save(path):
    git("add","--",str(path.relative_to(ROOT)))
    if not subprocess.run(["git","diff","--cached","--quiet"],cwd=ROOT).returncode:
        return
    git("commit","-m","Checkpoint 2026 Sky Notes draft "+path.stem)
    for attempt in range(8):
        try:
            git("push","origin","HEAD:main")
            return
        except subprocess.CalledProcessError:
            git("fetch","origin","main")
            git("rebase","origin/main")
            time.sleep(2*(attempt+1))
    raise RuntimeError("Cannot persist draft; stopping further API spending")
def main():
    if not MODEL:
        raise SystemExit("Set STORY_MODEL or MODEL to a verified API model ID")
    key=os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OPENAI_API_KEY secret unavailable: no paid calls made")
    report=json.loads((ROOT/"generated/story-research-queue-2026.json").read_text())
    registry=json.loads((ROOT/"database/fixed-objects.json").read_text())["fixed_objects"]
    byid={str(o["fixed_object_id"]):o for o in registry}
    todo=[x for x in report["objects"] if x["status"]=="needs-research" and any(START_WEEK <= int(str(w).split("W")[-1]) <= END_WEEK for w in x.get("weeks",[]) if str(w).split("W")[-1].isdigit())]
    todo.sort(key=lambda x:(min(x["weeks"]) if x["weeks"] else "9999",str(x["fixed_object_id"])))
    OUT.mkdir(parents=True,exist_ok=True)
    ledger_path=OUT/f"ledger-W{START_WEEK:02d}-W{END_WEEK:02d}.json"
    ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {"estimated_usd":0,"calls":[]}
    # The ledger may contain earlier batches: use a dedicated per-scope ledger for this run.
    git("config","user.name","github-actions[bot]")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    failures=[]
    skipped_existing=0
    for item in todo:
        ident=str(item["fixed_object_id"])
        if not re.fullmatch(r"[0-9]+",ident):
            raise RuntimeError("Unsafe fixed object ID")
        target=OUT/(ident+".json")
        if target.exists() or list((ROOT/"stories").glob("*/"+ident+".md")):
            skipped_existing+=1
            continue
        if ledger["estimated_usd"]+RESERVE>BUDGET:
            print("BUDGET STOP",ledger["estimated_usd"],flush=True)
            break
        obj=byid.get(ident)
        if obj is None:
            raise RuntimeError("Missing registry ID "+ident)
        facts={k:v for k,v in obj.items() if k in ("fixed_object_id","name","object_type","constellation","designation","aliases","source_records")}
        prompt=("Write a compelling evergreen Star Almanack draft for this fixed astronomical object. "
                "Return JSON with exactly hed, dek, body. Hed evocative and accurate; dek illuminating; "
                "body 250-400 words in developed paragraphs. Do not assert specific changing observing conditions. "
                "Use only reliable widely-known facts or supplied metadata; avoid unsupported distances, dates, "
                "magnitudes and invented history. When identity or facts are uncertain, write conservatively. "
                "No fake citations. This is an UNVERIFIED editorial draft, not publication-ready. "
                "Registry metadata: "+json.dumps(facts,ensure_ascii=False)[:7500])
        story=None
        for attempt in range(3):
            if ledger["estimated_usd"]+RESERVE>BUDGET:
                print("BUDGET STOP",ledger["estimated_usd"],flush=True)
                break
            payload=json.dumps({"model":MODEL,"input":prompt,"max_output_tokens":MAX_OUTPUT,
                "text":{"format":{"type":"json_schema","name":"story","strict":True,
                "schema":{"type":"object","properties":{"hed":{"type":"string"},"dek":{"type":"string"},"body":{"type":"string"}},"required":["hed","dek","body"],"additionalProperties":False}}}}).encode()
            req=urllib.request.Request("https://api.openai.com/v1/responses",data=payload,
                headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
            try:
                with urllib.request.urlopen(req,timeout=120) as response:
                    result=json.load(response)
            except urllib.error.HTTPError as err:
                raise RuntimeError("API returned HTTP "+str(err.code)) from err
            usage=result.get("usage",{})
            # Charge against conservative rates; reserve full call even if usage missing.
            cost=max((usage.get("input_tokens",MAX_INPUT)*INPUT_RATE+
                      usage.get("output_tokens",MAX_OUTPUT)*OUTPUT_RATE)/1e6,0)
            ledger["estimated_usd"]+=cost
            ledger["calls"].append({"id":ident,"reserved_estimate_usd":cost})
            # Persist ledger before next paid call, including if output malformed.
            ledger_path.write_text(json.dumps(ledger,indent=2)+"\n")
            save(ledger_path)
            raw="".join(c.get("text","") for o in result.get("output",[]) for c in o.get("content",[]) if c.get("type")=="output_text")
            try:
                story=json.loads(raw)
            except (ValueError, TypeError):
                print("INVALID JSON",ident,"attempt",attempt+1,flush=True)
                continue
            if not all(isinstance(story.get(k),str) and story[k].strip() for k in ("hed","dek","body")):
                print("INVALID STORY",ident,"attempt",attempt+1,flush=True)
                story=None
                continue
            break
        if story is None or not all(isinstance(story.get(k),str) and story[k].strip() for k in ("hed","dek","body")):
            failures.append(ident)
            print("SKIPPED AFTER RETRIES",ident,flush=True)
            continue
        target.write_text(json.dumps({"fixed_object_id":ident,"status":"draft_unverified",
            "weeks":item["weeks"],"hed":story["hed"],"dek":story["dek"],"body":story["body"]},
            ensure_ascii=False,indent=2)+"\n")
        save(target)
        print("SAVED",ident,"ESTIMATED RESERVED USD",round(ledger["estimated_usd"],4),flush=True)
    print(f"QUEUE {len(todo)}; REUSED EXISTING {skipped_existing}; NEWLY GENERATED {len(todo)-skipped_existing-len(failures)} (subject to budget stop)",flush=True)
    print("DRAFT RUN FINISHED; FAILED IDS:",",".join(failures) if failures else "none",flush=True)
if __name__=="__main__":
    main()
