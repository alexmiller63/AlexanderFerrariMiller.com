#!/usr/bin/env python3
"""Create a non-mutating editorial work queue from saved research progress.

This is a planning report, not an automatic fact-check or approval.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "research/story-progress-2026.json"

def make_queue(progress, week):
    key = f"W{week:02d}"
    data = progress.get("weeks", {}).get(key)
    if data is None:
        raise ValueError(f"No research progress recorded for {key}")
    tasks = []
    for fixed_id, record in sorted(data.get("objects", {}).items(), key=lambda x: int(x[0])):
        remaining = record.get("remaining", [])
        tasks.append({
            "target": fixed_id,
            "name": record.get("hed", ""),
            "source": record.get("source"),
            "stage": record.get("stage", "unreviewed"),
            "research_checked": record.get("research_checked", False),
            "finder_checked": record.get("finder_checked", False),
            "publication_checked": record.get("publication_checked", False),
            "remaining": remaining,
            "editorial_complete": record.get("stage") == "complete" and not remaining,
        })
    for blocked in data.get("blocked", []):
        tasks.append({
            "target": blocked.get("catalog_target_key"),
            "name": blocked.get("name"),
            "stage": blocked.get("stage", "blocked"),
            "blocked_reason": blocked.get("reason"),
            "remaining": blocked.get("remaining", []),
            "editorial_complete": False,
        })
    return {
        "schema_version": 1,
        "year": progress["year"],
        "week": key,
        "source_updated_at": progress.get("updated_at"),
        "total": len(tasks),
        "complete": sum(t["editorial_complete"] for t in tasks),
        "pending": sum(not t["editorial_complete"] for t in tasks),
        "tasks": tasks,
        "note": "Queue is informational. Never infer scientific or editorial approval from word counts or structural checks.",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("generated/editorial-queue.json"))
    args = parser.parse_args()
    if not 1 <= args.week <= 53:
        parser.error("week must be 1..53")
    report = make_queue(json.loads(SOURCE.read_text()), args.week)
    destination = args.output if args.output.is_absolute() else ROOT / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"{report['week']}: {report['complete']} complete, {report['pending']} pending; {destination}")

if __name__ == "__main__":
    main()
