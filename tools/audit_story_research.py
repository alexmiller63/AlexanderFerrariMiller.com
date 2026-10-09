#!/usr/bin/env python3
"""Inventory reusable story research before building a requested week range.

This is an editorial preflight, not an automatic research service. Catalogue
fallbacks do not count as completed Wordy stories. No public pages are written.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import fixed_object_stories as stories
from almanack_paths import week_index

MIN_WORDS = 500


def research_quality(story: stories.Story) -> list[str]:
    issues = []
    if len(story.body.split()) < MIN_WORDS:
        issues.append("needs substantial researched body (500+ words)")
    if len(re.split(r"\n\s*\n", story.body.strip())) < 5:
        issues.append("needs developed paragraphs")
    if not re.search(r"https?://|doi:\s*10\.", story.body, re.I):
        issues.append("needs traceable source URLs or DOIs")
    return issues


def coverage(pages: list[tuple[str, Path]]) -> dict:
    objects = {}
    missing_pages = []
    for label, page in pages:
        if not page.exists():
            missing_pages.append(label)
            continue
        for value in re.findall(r'\bdata-fixed-object-id="(\d+)"', page.read_text()):
            fixed_id = int(value)
            if fixed_id not in objects:
                meta = stories._fixed_object_meta(fixed_id)
                curated = [story for collection in sorted(stories.COLLECTIONS)
                           if (story := stories.read_story(collection, fixed_id)) is not None]
                # Existing fully researched built-in stories are reusable too.
                candidates = curated or [stories.baseline_story(fixed_id)]
                evaluated = [(story, research_quality(story)) for story in candidates]
                best, issues = min(evaluated, key=lambda item: len(item[1]))
                objects[fixed_id] = dict(
                    fixed_object_id=fixed_id, name=meta.get("name"),
                    object_type=meta.get("object_type_family"),
                    constellation=meta.get("constellation"),
                    weeks=[], status="needs-research" if issues else "ready",
                    issues=issues, body_words=len(best.body.split()),
                    existing_source=str(best.path.relative_to(stories.ROOT)),
                    suggested_source=f"stories/special-stars/{fixed_id}.md",
                    research_brief=(
                        "Resolve the permanent object identity before searching. Read primary "
                        "sources; write original prose covering physical nature, evidence and "
                        "uncertainties, naming/history where supported, finding instructions "
                        "and observing limits. Cite sources near their claims. Keep changing "
                        "weekly conditions out of the reusable story. Verify the accepted finder."
                    ),
                )
            if label not in objects[fixed_id]["weeks"]:
                objects[fixed_id]["weeks"].append(label)
    records = list(objects.values())
    return dict(schema_version=1, complete=not missing_pages and all(
        record["status"] == "ready" for record in records),
        missing_calendar_pages=missing_pages,
        ready=sum(record["status"] == "ready" for record in records),
        needs_research=sum(record["status"] != "ready" for record in records),
        objects=records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int)
    parser.add_argument("start_week", type=int)
    parser.add_argument("end_week", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.start_week <= args.end_week <= 53:
        parser.error("weeks must be an ascending range between 1 and 53")
    result = coverage([(f"{args.year}-W{week:02d}", week_index(args.year, week))
                       for week in range(args.start_week, args.end_week + 1)])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Story research: {result['ready']} ready; {result['needs_research']} need research; "
          f"{len(result['missing_calendar_pages'])} missing Calendar pages. Report: {args.output}")
    return 1 if args.require_complete and not result["complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
