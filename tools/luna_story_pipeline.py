#!/usr/bin/env python3
"""Three-stage research, writing and editorial audit. Dry-run unless --execute."""
import argparse
import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated" / "luna-pilot"
CAP = 1.00
TARGET = .10
MAX_INPUT = 6000
MAX_OUTPUT = 1200

def request_json(url, data=None, headers=None):
    req = Request(url, data=json.dumps(data).encode() if data is not None else None,
                  headers=headers or {"User-Agent": "StarAlmanackResearchPilot/1.0"},
                  method="POST" if data is not None else "GET")
    with urlopen(req, timeout=90) as response:
        return response.read().decode("utf-8", errors="replace")

def editorial_gate(task, research, draft, audit):
    """Conservative deterministic screening; never equates an AI audit with fact-checking."""
    sources = task.get("sources", [])
    checks = {
        "research_present": len(research.strip()) >= 150,
        "draft_length": 450 <= len(draft.split()) <= 650,
        "title_present": task["title"].lower() in draft.lower(),
        "source_citation": any(url in draft for url in sources),
        "audit_present": len(audit.strip()) >= 40,
        "no_placeholder": not re.search(r"\b(TODO|TBD|PLACEHOLDER)\b", draft, re.I),
    }
    # This screen can reject drafts but cannot establish factual accuracy.
    return {"screen_passed": all(checks.values()), "checks": checks,
            "publication_approved": False,
            "reason": "Independent source verification and editorial approval still required"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="research/luna-pilot-candidates.json")
    ap.add_argument("--model", required=True)
    ap.add_argument("--input-price", type=float, required=True, help="Verified USD per 1M input tokens")
    ap.add_argument("--output-price", type=float, required=True, help="Verified USD per 1M output tokens")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    if args.input_price <= 0 or args.output_price <= 0:
        ap.error("Verify positive pricing first")
    tasks = json.loads((ROOT / args.manifest).read_text())
    if len(tasks) != 10 or len({t["id"] for t in tasks}) != 10:
        ap.error("Expected 10 distinct tasks")
    OUT.mkdir(parents=True, exist_ok=True)
    ledger_file = OUT / "ledger.json"
    ledger = json.loads(ledger_file.read_text()) if ledger_file.exists() else {"estimated_usd": 0.0, "calls": []}
    print(json.dumps({"mode": "execute" if args.execute else "dry-run", "tasks": len(tasks),
                      "estimated_usd": ledger["estimated_usd"]}))
    if not args.execute:
        return
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        ap.error("OPENAI_API_KEY not configured")
    # Conservative per-call reserve: 25% margin. This is NOT an account-level billing cap.
    reserve = 1.25 * (MAX_INPUT * args.input_price + MAX_OUTPUT * args.output_price) / 1_000_000
    def ask(stage, instruction, source):
        if ledger["estimated_usd"] + reserve > CAP:
            raise RuntimeError("Application spending reservation exceeds $1 ceiling; stopping")
        prompt = instruction + "\n\n" + source
        if len(prompt) > 18000:
            prompt = prompt[:18000]
        payload = {"model": args.model, "input": prompt, "max_output_tokens": MAX_OUTPUT}
        raw = request_json("https://api.openai.com/v1/responses", payload,
                           {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        result = json.loads(raw)
        usage = result.get("usage", {})
        cost = (usage.get("input_tokens", MAX_INPUT) * args.input_price +
                usage.get("output_tokens", MAX_OUTPUT) * args.output_price) / 1_000_000
        ledger["estimated_usd"] += cost
        ledger["calls"].append({"stage": stage, "estimated_usd": cost,
                                "input_tokens": usage.get("input_tokens"),
                                "output_tokens": usage.get("output_tokens")})
        ledger_file.write_text(json.dumps(ledger, indent=2) + "\n")
        output = result.get("output_text") or "\n".join(
            part.get("text", "") for item in result.get("output", [])
            for part in item.get("content", []) if part.get("type") == "output_text")
        if not output.strip():
            raise RuntimeError("Empty model output at " + stage)
        return output.strip()
    for task in tasks:
        ident = str(task["id"])
        if not re.fullmatch(r"[0-9]+", ident):
            raise RuntimeError("Unsafe fixed-object ID")
        # Any story with this permanent ID, in any collection, is protected.
        if list((ROOT / "stories").glob("*/" + ident + ".md")):
            print("SKIP: existing story", ident)
            continue
        dest = OUT / (ident + ".md")
        if dest.exists():
            print("SKIP: already generated", ident)
            continue
        if ledger["estimated_usd"] + reserve * 3 > CAP:
            print("STOP: cannot reserve 3 stages within budget")
            break
        # No search tool is implied: retrieve provided sources and require evidence.
        evidence = []
        for url in task["sources"][:3]:
            if not url.startswith("https://"):
                raise RuntimeError("Non-HTTPS source")
            try:
                page = request_json(url)
                clean = re.sub(r"<[^>]+>", " ", page)
                clean = re.sub(r"\s+", " ", clean)
                evidence.append({"url": url, "excerpt": clean[:7000]})
            except Exception as exc:
                print("Source unavailable:", url, type(exc).__name__)
        if not evidence:
            print("SKIP: no retrievable research evidence", ident)
            continue
        basis = json.dumps({"task": task, "retrieved_sources": evidence}, ensure_ascii=False)
        research = ask(ident + ":research",
                       "Extract only supported, attributable astronomy facts. Cite exact URLs. "
                       "Flag uncertain or missing claims. Do not invent facts.", basis)
        draft = ask(ident + ":draft",
                    "Write an original 450-650 word Star Almanack story with hed, dek, "
                    "scientific context and observing guidance. The exact subject name "
                    f"{task['title']!r} must appear in the hed or opening paragraph. "
                    "Cite source URLs. Do not invent sources or assert publication review.", research))
        audit = ask(ident + ":audit",
                    "Audit the draft against the research. Identify unsupported facts, "
                    "missing citations, and ambiguities. Return a concise checklist; "
                    "do not declare verified publication.", research + "\n\nDRAFT:\n" + draft)
        # One bounded correction pass, only if deterministic screening fails.
        initial_gate = editorial_gate(task, research, draft, audit)
        if not initial_gate["screen_passed"] and ledger["estimated_usd"] + reserve * 2 <= CAP:
            revised = ask(ident + ":correction",
                          "Revise this draft to address the listed structural issues. "
                          "Use only facts supported by the research. Preserve accurate citations. "
                          "Return the complete 450-650 word story, without commentary.",
                          json.dumps(initial_gate["checks"]) + "\\nRESEARCH:\\n" +
                          research + "\\nDRAFT:\\n" + draft)
            revised_audit = ask(ident + ":reaudit",
                                "Independently audit this revised story against the supplied research. "
                                "Identify unsupported claims and missing citations.",
                                research + "\\nDRAFT:\\n" + revised)
            draft, audit = revised, revised_audit
        # Exclusive create, never replace existing work. Audit is saved separately.
        with dest.open("x", encoding="utf-8") as f:
            f.write(draft + "\n")
        (OUT / (ident + ".audit.txt")).write_text(audit + "\n")
        (OUT / (ident + ".research.txt")).write_text(research + "\n")
        gate = editorial_gate(task, research, draft, audit)
        (OUT / (ident + ".gate.json")).write_text(json.dumps(gate, indent=2) + "\n")
        print("DRAFT", ident, "screen_passed", gate["screen_passed"],
              "publication_approved", gate["publication_approved"],
              "estimated USD", round(ledger["estimated_usd"], 6))
        if ledger["estimated_usd"] >= TARGET:
            print("PAUSE: $0.10 target reached")
            break

if __name__ == "__main__":
    main()
