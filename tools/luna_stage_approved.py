#!/usr/bin/env python3
"""Stage independently approved Luna stories; never overwrite or publish by default."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "generated/luna-editorial"
SOURCE_ROOT = (BASE / "stories").resolve()
TARGET_ROOT = (ROOT / "stories").resolve()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Stage eligible stories; default is dry-run")
    args = parser.parse_args()
    decision = json.loads((BASE / "publication-decision.json").read_text(encoding="utf-8"))
    queue = {str(x["task_id"]): x for x in json.loads((BASE / "review-queue.json").read_text(encoding="utf-8"))["stories"]}
    staged = []
    for row in decision["stories"]:
        if row["blockers"] or row["approved"] is not True:
            continue
        record = queue[str(row["task_id"])]
        if not record.get("fixed_object_id") or not record.get("prepared_path"):
            raise ValueError("Missing permanent identity or prepared path")
        source = (ROOT / record["prepared_path"]).resolve()
        if not source.is_relative_to(SOURCE_ROOT) or not source.is_file():
            raise ValueError("Prepared manuscript missing or outside editorial staging")
        target = (TARGET_ROOT / source.relative_to(SOURCE_ROOT)).resolve()
        if not target.is_relative_to(TARGET_ROOT):
            raise ValueError("Unsafe target path")
        if target.exists():
            staged.append({"task_id":row["task_id"],"status":"existing story preserved","path":str(target.relative_to(ROOT))})
            continue
        manuscript = source.read_text(encoding="utf-8")
        if f"fixed_object_id: {record['fixed_object_id']}" not in manuscript or "status: pending" not in manuscript:
            raise ValueError("Manuscript identity or status mismatch")
        if args.write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(manuscript, encoding="utf-8")
        staged.append({"task_id":row["task_id"],"status":"staged pending" if args.write else "would stage pending","path":str(target.relative_to(ROOT))})
    print(json.dumps({"write":args.write,"staged":staged,"published":0},indent=2))

if __name__ == "__main__":
    main()
