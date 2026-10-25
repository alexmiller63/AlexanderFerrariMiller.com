#!/usr/bin/env python3
"""Read-only inventory of numbered Pilot Markdown stories."""
from pathlib import Path
import argparse
import json
import re

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--output", default="story-count.json")
    args = parser.parse_args()
    root = Path(args.root)
    directories = [p for p in root.rglob("luna-pilot") if p.is_dir() and ".git" not in p.parts]
    if not directories:
        raise SystemExit("No luna-pilot directory found; no report written.")
    files = sorted({p.resolve() for d in directories for p in d.rglob("*.md") if re.fullmatch(r"[0-9]+\.md", p.name)})
    nonempty = [p for p in files if p.stat().st_size > 0]
    empty = [p for p in files if p.stat().st_size == 0]
    ids = sorted({p.stem for p in files}, key=int)
    report = {
        "directories": [str(d.relative_to(root)) for d in directories],
        "numbered_markdown_files": len(files),
        "unique_story_ids": len(ids),
        "nonempty_files": len(nonempty),
        "empty_files": len(empty),
        "story_ids": ids,
        "empty_paths": [str(p.relative_to(root.resolve())) for p in empty],
        "note": "Nonempty does not imply validated or published."
    }
    print(json.dumps({k:v for k,v in report.items() if k not in ("story_ids","empty_paths")}, indent=2))
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
