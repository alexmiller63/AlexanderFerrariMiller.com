#!/usr/bin/env python3
"""Publish saved Luna Markdown as clearly labelled drafts under permanent object IDs.

Does not approve manuscripts, overwrite curated stories, or call paid services.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from fixed_object_stories import Story, COLLECTIONS, write_public_story

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    registry = json.loads((ROOT / "database/fixed-objects.json").read_text(encoding="utf-8"))
    valid = {int(o["fixed_object_id"]) for o in registry["fixed_objects"]}
    tasks = json.loads((ROOT / "research/luna-pilot-candidates.json").read_text(encoding="utf-8"))
    from luna_story_pipeline import resolve_objects
    mapping = resolve_objects(tasks)
    source = ROOT / "generated/luna-pilot"
    count = 0
    skipped = 0
    for path in sorted(source.glob("*.md")):
        task_id = path.stem
        if not task_id.isdigit():
            continue
        permanent_id = int(mapping.get(task_id, task_id))
        if permanent_id not in valid:
            print(f"SKIP unknown permanent ID: {path.name}")
            skipped += 1
            continue
        if any((ROOT / "stories" / collection / f"{permanent_id}.md").exists()
               for collection in COLLECTIONS):
            print(f"SKIP curated story exists: {permanent_id}")
            skipped += 1
            continue
        text = path.read_text(encoding="utf-8").strip()
        match = re.match(r"^#\s+(.+?)\s*\n+(.*)$", text, flags=re.S)
        if not match:
            print(f"SKIP malformed Markdown: {path.name}")
            skipped += 1
            continue
        title, rest = match.groups()
        sections = re.split(r"\n\s*\n", rest.strip(), maxsplit=1)
        if len(sections) < 2 or not sections[1].strip():
            print(f"SKIP incomplete draft: {path.name}")
            skipped += 1
            continue
        story = Story("drafts", permanent_id, path, title.strip(),
                      " ".join(sections[0].splitlines()), sections[1].strip(),
                      status="pending")
        target = ROOT / "stories/drafts" / f"{permanent_id}.html"
        if args.dry_run:
            print(f"READY {path.relative_to(ROOT)} -> {target.relative_to(ROOT)}")
        else:
            write_public_story(story)
            print(f"PUBLISHED DRAFT {target.relative_to(ROOT)}")
        count += 1
    print(f"Drafts: {count}; skipped: {skipped}; no review approvals granted")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
