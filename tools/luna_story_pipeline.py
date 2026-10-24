#!/usr/bin/env python3
"""Three-stage research, writing and editorial audit. Dry-run unless --execute."""
import argparse
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from html import unescape
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated" / "luna-pilot"
CAP = 2.00  # Only draft and optional correction invoke the paid API.
MAX_INPUT = 6000
MAX_OUTPUT = 4000
MAX_RETRY_OUTPUT = 8000
MAX_ATTEMPTS = 3

class StoryResponseError(RuntimeError):
    """This story could not produce a complete response after bounded retries."""

class BudgetExceeded(RuntimeError):
    """Stop the batch before spending beyond its application budget."""

class APIRequestError(RuntimeError):
    def __init__(self, message, status, code):
        super().__init__(message)
        self.retryable = status in (408, 409, 429) or status >= 500
        if code in ("insufficient_quota", "billing_hard_limit_reached"):
            self.retryable = False

def request_json(url, data=None, headers=None):
    req = Request(url, data=json.dumps(data).encode() if data is not None else None,
                  headers=headers or {"User-Agent": "StarAlmanackResearchPilot/1.0"},
                  method="POST" if data is not None else "GET")
    try:
        with urlopen(req, timeout=90) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        # API errors can explain a 404; never print request headers or credentials.
        body = exc.read(4096).decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("error", {})
            message = detail.get("message", "No API error message")
            code = detail.get("code", "unknown")
            error_type = detail.get("type", "unknown")
        except (ValueError, AttributeError):
            message, code, error_type = "Non-JSON error response", "unknown", "unknown"
        raise APIRequestError(f"HTTP {exc.code} from {req.full_url.split('?')[0]}: "
                           f"type={error_type}, code={code}, message={message}", exc.code, code) from None

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
        if pilot_id in resolved:
            raise RuntimeError("Duplicate task ID: " + pilot_id)
        if not re.fullmatch(r"[0-9]+", pilot_id):
            raise RuntimeError("Unsafe pilot task ID: " + pilot_id)
        if "identity" in task:
            identity = task["identity"]
            registry = json.loads((ROOT / "database/fixed-object-registry.json").read_text())["fixed_objects"]
            matches = [obj["fixed_object_id"] for obj in registry
                       if obj.get("status") == "active" and any(
                           ident.get("namespace") == identity.get("namespace") and
                           str(ident.get("value")) == str(identity.get("value"))
                           for ident in obj.get("identifiers", []))]
            if len(matches) != 1 or str(matches[0]) != pilot_id or task.get("fixed_object_id") != matches[0]:
                raise RuntimeError(f"Catalogue identity does not uniquely match permanent task {pilot_id}: {matches}")
        else:
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
    changed = git("diff", "--cached", "--name-only").stdout.strip()
    if not changed:
        return
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

def save_or_recover_evidence(path, retrieved, ledger_file, persist=None):
    """Persist source snapshots and reuse the original on restart."""
    if persist is None:
        persist = persist_checkpoint
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

def paid_story_response(stage, instruction, source, model, key, input_price,
                        output_price, ledger, ledger_file, output_dir=None):
    """Retry only recoverable request/output failures; account and persist every attempt."""
    prompt = (instruction + "\n\n" + source)[:18000]
    limit = MAX_OUTPUT
    last_error = "No response"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        reserve = 1.25 * (MAX_INPUT * input_price + limit * output_price) / 1_000_000
        if ledger["estimated_usd"] + reserve > CAP:
            raise BudgetExceeded("Application spending reservation exceeds $2.00 ceiling")
        diagnostic_path = (output_dir or OUT) / (stage.replace(":", ".") + "." + uuid.uuid4().hex + ".response.json")
        diagnostic = {"stage": stage, "model": model, "attempt": attempt,
                      "max_output_tokens": limit, "run_id": os.environ.get("GITHUB_RUN_ID")}
        result = None
        output = ""
        retryable = False
        fatal = None
        cost = reserve  # Unknown usage is charged conservatively, including timeouts.
        try:
            raw = request_json("https://api.openai.com/v1/responses",
                               {"model": model, "input": prompt, "max_output_tokens": limit},
                               {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            diagnostic["response_body"] = raw.replace(key, "[REDACTED]")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Expected a JSON response object")
            result = parsed
            usage = result.get("usage") or {}
            if "input_tokens" in usage and "output_tokens" in usage:
                cost = (usage["input_tokens"] * input_price + usage["output_tokens"] * output_price) / 1_000_000
            output = result.get("output_text") or "\n".join(
                part.get("text", "") for item in result.get("output", [])
                for part in item.get("content", []) if part.get("type") == "output_text")
            if result.get("status") != "completed" or not output.strip():
                last_error = ("Incomplete response" if result.get("status") != "completed"
                              else "Empty model output")
                retryable = True
                if (result.get("incomplete_details") or {}).get("reason") == "max_output_tokens":
                    limit = min(limit * 2, MAX_RETRY_OUTPUT)
        except APIRequestError as exc:
            retryable = exc.retryable
            last_error = str(exc).replace(key, "[REDACTED]")
            if not retryable:
                fatal = exc
        except (TimeoutError, URLError, ValueError) as exc:
            retryable = True
            last_error = str(exc).replace(key, "[REDACTED]")
        except Exception as exc:
            fatal = exc
            last_error = str(exc).replace(key, "[REDACTED]")
        if retryable or fatal:
            diagnostic["error"] = last_error
        ledger["estimated_usd"] += cost
        ledger["calls"].append({"stage": stage, "attempt": attempt, "estimated_usd": cost,
                                "usage_estimated": not bool(result and all(k in (result.get("usage") or {}) for k in ("input_tokens", "output_tokens"))),
                                "input_tokens": (result.get("usage") or {}).get("input_tokens") if result else None,
                                "output_tokens": (result.get("usage") or {}).get("output_tokens") if result else None,
                                "max_output_tokens": diagnostic["max_output_tokens"],
                                "status": result.get("status") if result else "request_error"})
        diagnostic_path.write_text(json.dumps(diagnostic, indent=2) + "\n", encoding="utf-8")
        ledger_file.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
        persist_checkpoint(diagnostic_path, ledger_file)
        if fatal:
            raise fatal
        if not retryable:
            return output.strip()
        if attempt < MAX_ATTEMPTS:
            print("RETRY", stage, attempt, last_error, flush=True)
            time.sleep(2 ** (attempt - 1))
    raise StoryResponseError(f"{stage}: {last_error}; {MAX_ATTEMPTS} attempts saved")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="research/luna-pilot-candidates.json")
    ap.add_argument("--model", required=True)
    ap.add_argument("--input-price", type=float, required=True, help="Verified USD per 1M input tokens")
    ap.add_argument("--output-price", type=float, required=True, help="Verified USD per 1M output tokens")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--repair-truncated", action="store_true",
                    help="Write replacement drafts separately; preserve originals and share the spending ledger")
    args = ap.parse_args()
    if args.input_price <= 0 or args.output_price <= 0:
        ap.error("Verify positive pricing first")
    tasks = json.loads((ROOT / args.manifest).read_text())
    if not tasks or len({str(t["id"]) for t in tasks}) != len(tasks):
        ap.error("Expected a nonempty manifest of distinct tasks")
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
    work_out = OUT / "repairs" if args.repair_truncated else OUT
    work_out.mkdir(parents=True, exist_ok=True)
    # Conservative per-call reserve: 25% margin. This is NOT an account-level billing cap.
    reserve = 1.25 * (MAX_INPUT * args.input_price + MAX_OUTPUT * args.output_price) / 1_000_000
    def ask(stage, instruction, source):
        return paid_story_response(stage, instruction, source, args.model, key,
                                   args.input_price, args.output_price, ledger, ledger_file, output_dir=work_out)
    def stage(ident, name, instruction, source):
        """Resume a completed paid stage without calling the API again."""
        path = work_out / (ident + "." + name + ".stage.txt")
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
        dest = work_out / (ident + ".md")
        if dest.exists():
            print("SKIP: already generated", ident)
            continue
        if ledger["estimated_usd"] + reserve * sum(not (work_out / (ident + "." + name + ".stage.txt")).exists() for name in ("draft", "correction")) > CAP:
            print("STOP: cannot reserve paid writing stages within budget")
            break
        evidence_path = work_out / (ident + ".evidence.json")
        original_evidence = OUT / (ident + ".evidence.json")
        if args.repair_truncated and not evidence_path.exists():
            # Fail closed if the evidence behind the original attempt is missing.
            evidence = json.loads(original_evidence.read_text(encoding="utf-8"))
            evidence = save_or_recover_evidence(evidence_path, evidence, ledger_file)
            print("REUSE original evidence", ident, flush=True)
        elif evidence_path.exists():
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
        try:
            draft = stage(ident, "draft",
                        "Write an original 450-650 word Star Almanack story with hed, dek, "
                        "scientific context and observing guidance. The exact subject name "
                        f"{task['title']!r} must appear in the hed or opening paragraph. "
                        "Cite source URLs. Do not invent sources or assert publication review.", research)
            audit = "Free deterministic review only; factual claims require independent editorial verification."
            # One bounded correction pass, only if deterministic screening fails.
            initial_gate = editorial_gate(task, research, draft, audit)
            if not initial_gate["screen_passed"] and (ledger["estimated_usd"] + reserve <= CAP or (work_out / (ident + ".correction.stage.txt")).exists()):
                revised = stage(ident, "correction",
                              "Revise this draft to address the listed structural issues. "
                              "Use only facts supported by the research. Preserve accurate citations. "
                              "Return the complete 450-650 word story, without commentary.",
                              json.dumps(initial_gate["checks"]) + "\\nRESEARCH:\\n" +
                              research + "\\nDRAFT:\\n" + draft)
                draft = revised
                audit = "Free deterministic review only; factual claims require independent editorial verification."
        except StoryResponseError as exc:
            failure_path = work_out / (ident + ".failure.json")
            failure_path.write_text(json.dumps({
                "object_id": ident, "reason": str(exc),
                "run_id": os.environ.get("GITHUB_RUN_ID"),
                "status": "retry_exhausted", "publication_approved": False,
            }, indent=2) + "\n", encoding="utf-8")
            persist_checkpoint(failure_path, ledger_file)
            print("SKIP: response retries exhausted", ident, str(exc), flush=True)
            continue
        except BudgetExceeded:
            print("STOP: application spending reservation exceeds $2.00 ceiling", flush=True)
            break
        # Exclusive create, never replace existing work. Audit is saved separately.
        with dest.open("x", encoding="utf-8") as f:
            f.write(draft + "\n")
        (work_out / (ident + ".audit.txt")).write_text(audit + "\n")
        (work_out / (ident + ".research.txt")).write_text(research + "\n")
        gate = editorial_gate(task, research, draft, audit)
        gate["source_verification"] = verify_source_evidence(task, research, draft, evidence)
        gate["claim_evidence_review"] = claim_evidence_review(research, draft, evidence)
        gate["evidence_support_matrix"] = evidence_support_matrix(draft, evidence)
        gate["exact_source_claim_check"] = exact_source_claim_check(draft, evidence)
        (work_out / (ident + ".gate.json")).write_text(json.dumps(gate, indent=2) + "\n")
        for completed in (dest.with_suffix(".audit.txt"), dest.with_suffix(".research.txt"),
                          dest.with_suffix(".gate.json"), dest):
            persist_checkpoint(completed, ledger_file)
        print("DRAFT", ident, "screen_passed", gate["screen_passed"],
              "publication_approved", gate["publication_approved"],
              "estimated USD", round(ledger["estimated_usd"], 6))

if __name__ == "__main__":
    main()
