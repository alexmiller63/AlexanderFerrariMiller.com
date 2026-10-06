#!/usr/bin/env python3
"""Fail the Sky Notes build if a human story link is missing or still routes to JSON."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from almanack_paths import week_index
from iso_date_range import parse_iso_date, weeks_in_range

start = parse_iso_date(sys.argv[1])
end = parse_iso_date(sys.argv[2])
checked = 0
empty_states = 0
pages_checked = 0

for iso_week in weeks_in_range(start, end):
    year, week = iso_week.year, iso_week.week
    page = week_index(year, week)
    if not page.exists():
        raise SystemExit(f"Missing weekly Sky Notes page: {page}")

    text = page.read_text(encoding="utf-8")
    pages_checked += 1

    source = Path("generated-sky-notes") / str(year) / f"W{week:02d}.json"
    if not source.exists():
        raise SystemExit(f"{page}: missing generated Sky Notes source {source}")

    payload = json.loads(source.read_text(encoding="utf-8"))
    fixed_ids = [str(item["fixed_object_id"]) for item in payload.get("fixed_sky") or [] if item.get("fixed_object_id")]

    # The generated source is the contract between discovery and presentation.
    # linked_stories is intentionally a presentation subset: stories for objects
    # already named in the observing guide are suppressed from More Sky Notes.
    # Every linked story must still be a discovered candidate and must resolve to
    # a reader-facing human page.
    candidates = payload.get("story_candidates")
    linked_stories = payload.get("linked_stories")
    if candidates is None or linked_stories is None:
        raise SystemExit(f"{page}: generated source lacks story_candidates/linked_stories contract")

    candidate_keys = {
        (str(story.get("fixed_object_id")), str(story.get("collection")), str(story.get("url")))
        for story in candidates
    }
    linked_keys = {
        (str(story.get("fixed_object_id")), str(story.get("collection")), str(story.get("url")))
        for story in linked_stories
    }
    if not linked_keys.issubset(candidate_keys):
        extra = sorted(linked_keys - candidate_keys)
        raise SystemExit(
            f"{page}: linked story set contains stories not discovered as candidates; extra={extra}"
        )

    for story in linked_stories:
        human = str(story.get("url") or "")
        if not human:
            raise SystemExit(f"{page}: linked story has no human URL: {story}")
        target = Path(human.lstrip("/"))
        if not target.exists():
            raise SystemExit(f"{page}: missing linked human story target {human}")
        reader_human = "../../../" + human.lstrip("/") if human.startswith("/stories/") else human
        if f'href="{reader_human}"' not in text:
            raise SystemExit(
                f"{page}: missing reader-facing story link {reader_human} "
                f"for object {story.get('fixed_object_id')}"
            )

    if not fixed_ids:
        empty_state = "No deep-sky objects are featured this week."
        if empty_state not in text:
            raise SystemExit(f"{page}: no deep-sky objects found and reader-facing empty state is missing")
        empty_states += 1
        continue

    for fixed_id in dict.fromkeys(fixed_ids):
        descriptor = Path("almanack/descriptors") / f"{fixed_id}.json"
        if not descriptor.exists():
            raise SystemExit(f"{page}: missing descriptor {fixed_id}")

        record = json.loads(descriptor.read_text(encoding="utf-8"))
        human = (record.get("representation") or {}).get("human")
        if not human:
            raise SystemExit(f"{page}: descriptor {fixed_id} has no human representation")

        target = Path(human.lstrip("/"))
        if not target.exists():
            raise SystemExit(f"{page}: missing human target {human}")

        reader_human = "../../../" + human.lstrip("/") if human.startswith("/stories/") else human
        if f'href="{reader_human}"' not in text:
            raise SystemExit(f"{page}: missing reader-facing link {reader_human} for object {fixed_id}")

        json_link_patterns = (
            f'href="/almanack/descriptors/{fixed_id}.json"',
            f'href="../../../almanack/descriptors/{fixed_id}.json"',
            f'href="../../almanack/descriptors/{fixed_id}.json"',
            f'href="../almanack/descriptors/{fixed_id}.json"',
        )
        if any(pattern in text for pattern in json_link_patterns):
            raise SystemExit(f"{page}: reader-facing fixed-object link still points to JSON for {fixed_id}")

        checked += 1

if pages_checked == 0:
    raise SystemExit("No weekly Sky Notes pages were verified")

print(
    f"Verified {checked} descriptor human mapping(s), deduplicated generated story-link sets, "
    f"and {empty_states} explicit no-deep-sky state(s)"
)
