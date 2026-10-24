#!/usr/bin/env python3
"""Select only saved final drafts with direct evidence of token-limit truncation."""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote
try:
    from tools.select_missing_story_candidates import registry_identity
except ModuleNotFoundError:
    from select_missing_story_candidates import registry_identity

ROOT = Path(__file__).resolve().parents[1]


def response_text(response):
    return (response.get("output_text") or "\n".join(
        part.get("text", "") for item in response.get("output", [])
        for part in item.get("content", []) if part.get("type") == "output_text")).strip()


def select_repairs(root=ROOT, limit=1000):
    saved = root / "generated/luna-pilot"
    registry = json.loads((root / "database/fixed-object-registry.json").read_text())["fixed_objects"]
    active = {str(obj["fixed_object_id"]): obj for obj in registry if obj.get("status") == "active"}
    objects = json.loads((root / "database/fixed-objects.json").read_text())["fixed_objects"]
    objects = {str(obj["fixed_object_id"]): obj for obj in objects}
    affected = {}
    for path in sorted(saved.glob("*.response.json")):
        diagnostic = json.loads(path.read_text())
        if "response_body" not in diagnostic:
            continue
        try:
            response = json.loads(diagnostic["response_body"])
        except (TypeError, ValueError):
            continue
        if not isinstance(response, dict):
            continue
        if response.get("status") != "incomplete" or (response.get("incomplete_details") or {}).get("reason") != "max_output_tokens":
            continue
        stage = diagnostic.get("stage", "")
        match = re.fullmatch(r"(\d+):(draft|correction)", stage)
        if not match:
            continue
        ident = match.group(1)
        if (saved / "repairs" / (ident + ".md")).exists():
            continue
        final = saved / (ident + ".md")
        # Compare the final text, or the latest paid stage if finalization was interrupted.
        candidate = next((p for p in (final, saved / (ident + ".correction.stage.txt"),
                                      saved / (ident + ".draft.stage.txt")) if p.exists()), None)
        # An early attempt can be incomplete while a later correction is fine.
        if candidate and candidate.read_text().strip() != response_text(response):
            continue
        if not (saved / (ident + ".evidence.json")).exists():
            raise RuntimeError("Missing original evidence for repair " + ident)
        affected.setdefault(ident, []).append(str(path.relative_to(root)))
    selected, report = [], []
    for ident in sorted(affected, key=int)[:limit]:
        if ident not in active or ident not in objects:
            raise RuntimeError("Missing active permanent identity for repair " + ident)
        identity, query = registry_identity(active[ident])
        source = "https://simbad.cds.unistra.fr/simbad/sim-id?Ident=" + quote(query)
        evidence = json.loads((saved / (ident + ".evidence.json")).read_text())
        if not any(e.get("url") == source for e in evidence):
            raise RuntimeError("Original evidence does not match permanent identity for repair " + ident)
        name = next(((rec.get("facts") or {}).get("name") for rec in objects[ident].get("source_records", [])
                     if (rec.get("facts") or {}).get("name")), query)
        task = {"id": ident, "fixed_object_id": int(ident), "identity": identity,
                "title": str(name), "sources": [source],
                "facts": "Registry identity: " + query + ". Source catalog identity only; all other claims require verification."}
        task["repair_reason"] = "Saved final output exhausted max_output_tokens"
        task["repair_response_files"] = affected[ident]
        selected.append(task)
        report.append({"id": ident, "title": task["title"],
                       "original_draft_exists": (saved / (ident + ".md")).exists(),
                       "response_files": affected[ident]})
    return selected, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--output", default="generated/luna-pilot-selected.json")
    args = ap.parse_args()
    if not 1 <= args.limit <= 1000:
        ap.error("limit must be 1..1000")
    selected, report = select_repairs(limit=args.limit)
    if not selected:
        raise SystemExit("No token-limited drafts remain to repair; no paid calls needed")
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(selected, indent=2) + "\n")
    (ROOT / "generated/story-selection-preflight.json").write_text(json.dumps({
        "mode": "repair_truncated", "selected_count": len(selected), "stories": report,
        "originals_preserved": True, "shared_ledger": "generated/luna-pilot/ledger.json",
    }, indent=2) + "\n")
    print("TOKEN-LIMIT REPAIRS:", len(selected))
    for task in selected:
        print(task["id"], task["title"])


if __name__ == "__main__":
    main()
