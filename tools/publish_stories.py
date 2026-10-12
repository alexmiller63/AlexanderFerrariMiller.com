#!/usr/bin/env python3
"""Publish only reviewed, complete Star Almanack stories to their HTML reader pages.

This tool never edits story Markdown or grants completion attestations. The source
story must already carry a valid permanent object ID and all three review checks.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixed_object_stories import COLLECTIONS, read_story, write_public_story
from story_audit import audit_file

REQUIRED_CHECKS = ("research_checked", "finder_checked", "publication_checked")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate eligible stories without writing HTML.",
    )
    args = parser.parse_args()

    candidates = sorted(
        path
        for collection in COLLECTIONS
        for path in (ROOT / "stories" / collection).glob("*.md")
    )
    published = 0
    skipped = 0
    errors: list[str] = []

    for path in candidates:
        try:
            fixed_object_id = int(path.stem)
            story = read_story(path.parent.name, fixed_object_id)
            if story is None or story.status != "complete":
                skipped += 1
                continue

            audit = audit_file(path)
            if audit["structural_issues"]:
                raise ValueError("; ".join(audit["structural_issues"]))
            missing_checks = [key for key in REQUIRED_CHECKS if not audit["checks"][key]]
            if missing_checks:
                raise ValueError("missing review attestations: " + ", ".join(missing_checks))
            if not story.body.strip():
                raise ValueError("story body is empty")

            if args.dry_run:
                print(f"READY {path.relative_to(ROOT)} -> stories/{story.collection}/{fixed_object_id}.html")
            else:
                output = write_public_story(story)
                rendered = output.read_text(encoding="utf-8")
                for required in (
                    f'data-fixed-object-id="{fixed_object_id}"',
                    'data-story-field="hed"',
                    'data-story-field="dek"',
                    'data-story-field="body"',
                ):
                    if required not in rendered:
                        raise ValueError(f"rendered page missing required marker: {required}")
                print(f"PUBLISHED {output.relative_to(ROOT)}")
            published += 1
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")

    print(
        f"Summary: {published} eligible story/stories "
        f"{'validated' if args.dry_run else 'rendered'}; {skipped} pending story/stories skipped."
    )
    if errors:
        print("Publication errors:")
        for error in errors:
            print(f"ERROR {error}")
        return 1
    if published == 0:
        print("No complete stories were eligible. No review status was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
