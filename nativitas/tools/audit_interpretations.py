#!/usr/bin/env python3
"""Audit Nativitas aspect interpretations and produce a review queue.

This script does NOT claim to verify astrological sources or write interpretations.
"""
import argparse
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "aspect-interpretations.json"
REVIEWED = {"reviewed-against-online-reference", "approved"}
EXCLUDED = {"astronomically-unavailable"}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--batch-size", type=int, default=20)
    p.add_argument("--out", type=Path, default=Path("nativitas-review"))
    args = p.parse_args()
    if args.batch_size < 1:
        p.error("--batch-size must be positive")
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    planets, aspects = data["planet_order"], data["aspects"]
    expected = {(a, b, aspect) for i, a in enumerate(planets)
                for b in planets[i+1:] for aspect in aspects}
    found, errors, queue = set(), [], []
    counts = collections.Counter()
    for i, entry in enumerate(data["entries"]):
        key = (*entry.get("pair", []), entry.get("aspect"))
        if key in found:
            errors.append(f"Duplicate: {key}")
        found.add(key)
        if key not in expected:
            errors.append(f"Unexpected combination at index {i}: {key}")
        status = entry.get("status", "unspecified")
        counts[status] += 1
        if status in REVIEWED:
            if not entry.get("sources"):
                errors.append(f"Reviewed without sources: {key}")
            if not entry.get("text", "").strip():
                errors.append(f"Reviewed without text: {key}")
        elif status not in EXCLUDED:
            queue.append({"pair": entry.get("pair"), "aspect": entry.get("aspect"),
                          "status": status, "source_count": len(entry.get("sources", []))})
    for missing in sorted(expected - found):
        errors.append(f"Missing: {missing}")
    args.out.mkdir(parents=True, exist_ok=True)
    summary = {"total": len(data["entries"]), "status_counts": dict(sorted(counts.items())),
               "remaining_for_review": len(queue), "errors": errors,
               "note": "Automated structural audit only; source accuracy requires human editorial review."}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.out / "next-batch.json").write_text(json.dumps(queue[:args.batch_size], indent=2) + "\n")
    lines = ["# Nativitas interpretation audit", "",
             f"- Total entries: {summary['total']}",
             f"- Remaining for review: {len(queue)}",
             f"- Structural errors: {len(errors)}", "",
             "## Status counts", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(counts.items())]
    lines += ["", "## Next review batch", ""]
    lines += [f"- {', '.join(e['pair'])}: {e['aspect']} ({e['status']})" for e in queue[:args.batch_size]]
    lines += ["", "**This workflow does not research or verify interpretations automatically.**"]
    (args.out / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    if errors:
        raise SystemExit("Structural audit failed; see summary.json")

if __name__ == "__main__":
    main()
