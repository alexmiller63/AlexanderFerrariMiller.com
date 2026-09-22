#!/usr/bin/env python3
"""Fail the Sky Notes build if a human story link is missing or still routes to JSON."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from almanack_paths import sky_notes_page
from iso_date_range import parse_iso_date, weeks_in_range

start = parse_iso_date(sys.argv[1])
end = parse_iso_date(sys.argv[2])
checked = 0
empty_states = 0
pages_checked = 0

for iso_week in weeks_in_range(start, end):
    year, week = iso_week.year, iso_week.week
    page = sky_notes_page(year, week)
    if not page.exists():
        raise SystemExit(f"Missing weekly Sky Notes page: {page}")

    text = page.read_text(encoding="utf-8")
    pages_checked += 1

    source = Path("generated-sky-notes") / str(year) / f"W{week:02d}.json"
    if not source.exists():
        raise SystemExit(f"{page}: missing generated Sky Notes source {source}")

    payload = json.loads(source.read_text(encoding="utf-8"))
    deep_sky_ids = [
        str(item["fixed_object_id"])
        for item in payload.get("fixed_sky") or []
        if item.get("type") == "deep-sky"
    ]

    if not deep_sky_ids:
        empty_state = "No deep-sky objects are featured this week."
        if empty_state not in text:
            raise SystemExit(f"{page}: no deep-sky objects found and reader-facing empty state is missing")
        empty_states += 1
        continue

    for fixed_id in dict.fromkeys(deep_sky_ids):
        descriptor = Path("almanack/descriptors") / f"{fixed_id}.json"
        if not descriptor.exists():
            raise SystemExit(f"{page}: missing deep-sky descriptor {fixed_id}")

        record = json.loads(descriptor.read_text(encoding="utf-8"))
        if record.get("type") != "deep-sky-object":
            raise SystemExit(f"{page}: descriptor {fixed_id} is not a deep-sky-object")

        human = (record.get("representation") or {}).get("human")
        if not human:
            raise SystemExit(f"{page}: deep-sky descriptor {fixed_id} has no human representation")

        target = Path(human.lstrip("/"))
        if not target.exists():
            raise SystemExit(f"{page}: missing human target {human}")

        reader_human = "../../../" + human.lstrip("/") if human.startswith("/stories/") else human
        if f'href="{reader_human}"' not in text:
            raise SystemExit(f"{page}: missing reader-facing link {reader_human} for deep-sky object {fixed_id}")

        if f'href="/almanack/descriptors/{fixed_id}.json"' in text:
            raise SystemExit(f"{page}: reader-facing link still points to JSON for {fixed_id}")

        checked += 1

if pages_checked == 0:
    raise SystemExit("No weekly Sky Notes pages were verified")

print(
    f"Verified {checked} human deep-sky link(s) and {empty_states} explicit "
    "no-deep-sky state(s), descriptor mappings, and materialized targets"
)
