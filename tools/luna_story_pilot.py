#!/usr/bin/env python3
"""Opt-in, bounded Star Almanack story pilot. Never overwrites existing stories."""
import argparse
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated" / "luna-pilot"
PRICE = {"input": None, "output": None}  # Require verified pricing explicitly.

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True, help="JSON array of up to 10 {id,title,facts,sources} objects")
    p.add_argument("--model", required=True, help="Verified OpenAI API model ID")
    p.add_argument("--input-usd-per-million", type=float, required=True)
    p.add_argument("--output-usd-per-million", type=float, required=True)
    p.add_argument("--execute", action="store_true", help="Otherwise perform no API requests")
    args = p.parse_args()
    tasks = json.loads(Path(args.manifest).read_text())
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 10:
        raise SystemExit("Manifest must contain 1 to 10 tasks")
    if any(not isinstance(t, dict) or not all(t.get(k) for k in ("id", "title", "facts", "sources")) for t in tasks):
        raise SystemExit("Every task needs id, title, verified facts, and sources")
    if len({str(t["id"]) for t in tasks}) != len(tasks):
        raise SystemExit("Duplicate task IDs")
    if args.input_usd_per_million <= 0 or args.output_usd_per_million <= 0:
        raise SystemExit("Pricing must be positive and verified")
    OUT.mkdir(parents=True, exist_ok=True)
    ledger_path = OUT / "ledger.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {"spent_estimate_usd": 0, "calls": []}
    spent = float(ledger["spent_estimate_usd"])
    if not args.execute:
        print(json.dumps({"mode": "dry-run", "tasks": len(tasks), "existing_cost": spent, "api_calls": 0}))
        return
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise SystemExit("Missing OPENAI_API_KEY")
    for t in tasks:
        ident = str(t["id"])
        if not ident.replace("-", "").replace("_", "").isalnum():
            raise SystemExit("Unsafe task ID")
        dest = OUT / (ident + ".md")
        if dest.exists() or (ROOT / "stories" / "lunar" / (ident + ".md")).exists():
            print("SKIP existing", ident)
            continue
        # Reserve worst-case tokens (input <= 8k, output <= 2k), including safety margin.
        max_input, max_output = 8000, 2000
        reservation = 1.25 * (max_input * args.input_usd_per_million + max_output * args.output_usd_per_million) / 1_000_000
        if spent + reservation > 1.00:
            print("STOP: cannot safely reserve next call within $1.00 application budget")
            break
        prompt = ("Write one original, accurate Star Almanack story, 450-650 words, with a headline, "
                  "standfirst, readable astronomy and citations to the supplied sources. "
                  "Do not invent observations or sources. Distinguish uncertainty. "
                  "Use ONLY the supplied verified facts and sources. Never assert publication approval.\n"
                  + json.dumps(t, ensure_ascii=False))
        payload = {"model": args.model, "input": prompt, "max_output_tokens": max_output}
        req = Request("https://api.openai.com/v1/responses",
                      data=json.dumps(payload).encode(), method="POST",
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=120) as response:
                result = json.load(response)
        except HTTPError as exc:
            raise SystemExit("API error HTTP " + str(exc.code)) from None
        usage = result.get("usage", {})
        i, o = int(usage.get("input_tokens", max_input)), int(usage.get("output_tokens", max_output))
        cost = (i * args.input_usd_per_million + o * args.output_usd_per_million) / 1_000_000
        spent += cost
        ledger["spent_estimate_usd"] = spent
        ledger["calls"].append({"id": ident, "input_tokens": i, "output_tokens": o, "estimated_usd": cost})
        ledger_path.write_text(json.dumps(ledger, indent=2) + "\n")
        text = result.get("output_text") or "\n".join(
            c.get("text", "") for item in result.get("output", []) for c in item.get("content", [])
            if c.get("type") == "output_text")
        if not text.strip():
            print("No story returned for", ident)
            break
        # Exclusive create: never rewrite any existing file.
        with dest.open("x", encoding="utf-8") as f:
            f.write(text.strip() + "\n")
        print("DRAFT", ident, "estimated cumulative USD", round(spent, 6))
        if spent >= .10:
            print("TARGET reached; pause for review")
            break

if __name__ == "__main__":
    main()
