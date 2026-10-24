#!/usr/bin/env python3
"""Three-stage research, writing and editorial audit. Dry-run unless --execute."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from html import unescape
from html.parser import HTMLParser
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated" / "luna-pilot"
CAP = 1.00  # Only draft and optional correction invoke the paid API.
MAX_INPUT = 6000
MAX_OUTPUT = 1600

def request_json(url, data=None, headers=None):
    req = Request(url, data=json.dumps(data).encode() if data is not None else None,
                  headers=headers or {"User-Agent": "StarAlmanackResearchPilot/1.0"},
                  method="POST" if data is not None else "GET")
    with urlopen(req, timeout=90) as response:
        return response.read().decode("utf-8", errors="replace")

class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

def resolve_objects(tasks):
    """Preflight all catalogue identities before paid calls."""
    objects = json.loads((ROOT / "database/fixed-objects.json").read_text())["fixed_objects"]
    resolved = {}
    for task in tasks:
        pilot_id = str(task["id"])
        if not re.fullmatch(r"[0-9]+", pilot_id):
            raise RuntimeError("Unsafe pilot task ID: " + pilot_id)
        match = re.search(r"Registry identity:\s*HIP\s+(\d+)", task.get("facts", ""))
        if not match:
            raise RuntimeError("Missing HIP identity for pilot task " + pilot_id)
        hip = match.group(1)
        matches = [obj["fixed_object_id"] for obj in objects if any(
            re.search(r"\bHIP\s+" + re.escape(hip) + r"\b",
                      str(source.get("source_key", "")), re.I)
            for source in obj.get("source_records", []))]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one permanent object ID for task {pilot_id} (HIP {hip}); found {len(matches)}")
        resolved[pilot_id] = str(matches[0])
    if len(set(resolved.values())) != len(resolved):
        raise RuntimeError("Duplicate permanent object IDs in pilot manifest")
    return resolved

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

def verify_source_evidence(task, research, draft, evidence):
    """Independently check citation provenance against retrieved source pages."""
    retrieved = {entry["url"]: entry.get("excerpt", "") for entry in evidence}
    cited = [url for url in task.get("sources", []) if url in draft]
    checks = {
        "source_retrieved": bool(retrieved),
        "cited_source_retrieved": bool(cited) and all(
            url in retrieved and len(retrieved[url].strip()) >= 200 for url in cited),
        "research_cites_retrieved_source": any(url in research for url in retrieved),
        "draft_cites_retrieved_source": any(url in draft for url in retrieved),
    }
    return {"provenance_passed": all(checks.values()), "checks": checks,
            "factual_claims_verified": False,
            "reason": "URL provenance does not verify individual astronomical claims"}

def claim_evidence_review(research, draft, evidence):
    """Require human-readable claim/evidence mapping, without self-certifying truth."""
    urls = {entry["url"] for entry in evidence if len(entry.get("excerpt", "").strip()) >= 200}
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\\s+", draft)
                 if len(s.strip().split()) >= 7 and not s.strip().startswith("https://")]
    citations = [s for s in sentences if any(url in s for url in urls)]
    return {
        "substantive_sentences": len(sentences),
        "sentences_with_retrieved_source_url": len(citations),
        "source_urls": sorted(urls),
        "claims_independently_verified": False,
        "publication_ready": False,
        "reason": "Source attribution alone cannot prove each claim is supported by source text",
    }

def evidence_support_matrix(draft, evidence):
    """Produce a review queue of factual sentences and their possible sources.

    Candidate sources are NOT proof that a sentence is true.
    """
    sources = [(entry["url"], entry.get("excerpt", "")) for entry in evidence]
    lines = re.split(r"(?<=[.!?])\\s+", draft)
    claims = []
    for sentence in lines:
        sentence = sentence.strip()
        if len(sentence.split()) < 7 or sentence.startswith("https://"):
            continue
        words = {w.lower() for w in re.findall(r"[A-Za-z]{5,}", sentence)}
        candidates = []
        for url, excerpt in sources:
            content = excerpt.lower()
            overlap = sorted(w for w in words if w in content)
            if len(overlap) >= 3:
                candidates.append({"url": url, "overlap_terms": overlap[:12]})
        claims.append({"claim": sentence, "candidate_sources": candidates,
                       "verified": False})
    return {"claims": claims, "verified_claims": 0,
            "requires_independent_review": True}

def exact_source_claim_check(draft, evidence):
    """Deterministic quote validation; paraphrases require separate review."""
    sources = {e["url"]: re.sub(r"\\s+", " ", e.get("excerpt", "")).strip()
               for e in evidence}
    quotes = re.findall(r'["“]([^"”]{12,240})["”]', draft)
    results = []
    for quote in quotes:
        normalized = re.sub(r"\\s+", " ", quote).strip().casefold()
        matching = [url for url, excerpt in sources.items()
                    if normalized in excerpt.casefold()]
        results.append({"quoted_text": quote, "source_matches": matching,
                        "exact_text_confirmed": bool(matching)})
    return {"quoted_passages": results,
            "all_quoted_passages_confirmed": all(x["exact_text_confirmed"] for x in results),
            "paraphrased_claims_verified": False,
            "publication_approved": False}

def persist_checkpoint(path, ledger_file):
    """Commit and push each completed paid stage before spending on the next."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    branch = os.environ.get("GITHUB_REF_NAME", "")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch):
        raise RuntimeError("Unsafe or missing GitHub branch for checkpoint persistence")
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, check=True,
                              capture_output=True, text=True)
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "--", str(path.relative_to(ROOT)), str(ledger_file.relative_to(ROOT)))
    git("commit", "-m", "Checkpoint Luna paid stage " + path.name)
    for attempt in range(4):
        try:
            git("push", "origin", "HEAD:" + branch)
            print("PERSISTED", path.name, flush=True)
            return
        except subprocess.CalledProcessError:
            git("fetch", "origin", branch)
            git("rebase", "origin/" + branch)
    raise RuntimeError("Could not push paid-stage checkpoint; stopping before next API call")

def save_or_recover_evidence(path, retrieved, ledger_file, persist=persist_checkpoint):
    """Persist source snapshots and reuse the original on restart."""
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(saved, list) or not saved:
            raise RuntimeError("Invalid saved source evidence: " + str(path))
        return saved
    if not retrieved:
        raise RuntimeError("No source evidence to preserve")
    with path.open("x", encoding="utf-8") as handle:
        json.dump(retrieved, handle, ensure_ascii=False, indent=2)
        handle.write(chr(10))
    persist(path, ledger_file)
    return retrieved

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
    resolved = resolve_objects(tasks)
    print("Catalogue preflight:", len(resolved), "unique permanent object IDs")
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
    if not ledger_file.exists():
        ledger_file.write_text(json.dumps(ledger, indent=2) + chr(10))
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
    def stage(ident, name, instruction, source):
        """Resume a completed paid stage without calling the API again."""
        path = OUT / (ident + "." + name + ".stage.txt")
        if path.exists():
            saved = path.read_text(encoding="utf-8").strip()
            if not saved:
                raise RuntimeError("Empty stage checkpoint: " + str(path))
            print("RESUME", ident, name, flush=True)
            return saved
        output = ask(ident + ":" + name, instruction, source)
        with path.open("x", encoding="utf-8") as handle:
            handle.write(output + chr(10))
        print("CHECKPOINT", ident, name, flush=True)
        persist_checkpoint(path, ledger_file)
        return output

    for task in tasks:
        ident = resolved[str(task["id"])]
        if list((ROOT / "stories").glob("*/" + ident + ".md")):
            print("SKIP: existing story", ident)
            continue
        # Keep drafts separate from the permanent story collection until the
        # registry mapping and independent publication checks are complete.
        dest = OUT / (ident + ".md")
        if dest.exists():
            print("SKIP: already generated", ident)
            continue
        if ledger["estimated_usd"] + reserve * sum(not (OUT / (ident + "." + name + ".stage.txt")).exists() for name in ("draft", "correction")) > CAP:
            print("STOP: cannot reserve 3 stages within budget")
            break
        evidence_path = OUT / (ident + ".evidence.json")
        if evidence_path.exists():
            evidence = save_or_recover_evidence(evidence_path, [], ledger_file)
            print("RESUME", ident, "evidence", flush=True)
        else:
            evidence = []
            for url in task["sources"][:3]:
                if not url.startswith("https://"):
                    raise RuntimeError("Non-HTTPS source")
                try:
                    page = request_json(url)
                    parser = PageText()
                    parser.feed(page)
                    clean = unescape(" ".join(parser.parts))
                    clean = re.sub(r"\s+", " ", clean)
                    evidence.append({"url": url, "excerpt": clean[:7000]})
                except Exception as exc:
                    print("Source unavailable:", url, type(exc).__name__)
            if not evidence:
                print("SKIP: no retrievable research evidence", ident)
                continue
            evidence = save_or_recover_evidence(evidence_path, evidence, ledger_file)
        basis = json.dumps({"task": task, "retrieved_sources": evidence}, ensure_ascii=False)
        research = "Source evidence (automatically retrieved; not independently fact-checked):\n" + "\n".join(e["url"] + "\n" + e.get("excerpt", "") for e in evidence)
        draft = stage(ident, "draft",
                    "Write an original 450-650 word Star Almanack story with hed, dek, "
                    "scientific context and observing guidance. The exact subject name "
                    f"{task['title']!r} must appear in the hed or opening paragraph. "
                    "Cite source URLs. Do not invent sources or assert publication review.", research)
        audit = "Free deterministic review only; factual claims require independent editorial verification."
        # One bounded correction pass, only if deterministic screening fails.
        initial_gate = editorial_gate(task, research, draft, audit)
        if not initial_gate["screen_passed"] and (ledger["estimated_usd"] + reserve <= CAP or (OUT / (ident + ".correction.stage.txt")).exists()):
            revised = stage(ident, "correction",
                          "Revise this draft to address the listed structural issues. "
                          "Use only facts supported by the research. Preserve accurate citations. "
                          "Return the complete 450-650 word story, without commentary.",
                          json.dumps(initial_gate["checks"]) + "\\nRESEARCH:\\n" +
                          research + "\\nDRAFT:\\n" + draft)
            revised_audit = stage(ident, "reaudit",
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
        gate["source_verification"] = verify_source_evidence(task, research, draft, evidence)
        gate["claim_evidence_review"] = claim_evidence_review(research, draft, evidence)
        gate["evidence_support_matrix"] = evidence_support_matrix(draft, evidence)
        gate["exact_source_claim_check"] = exact_source_claim_check(draft, evidence)
        (OUT / (ident + ".gate.json")).write_text(json.dumps(gate, indent=2) + "\n")
        print("DRAFT", ident, "screen_passed", gate["screen_passed"],
              "publication_approved", gate["publication_approved"],
              "estimated USD", round(ledger["estimated_usd"], 6))

if __name__ == "__main__":
    main()
