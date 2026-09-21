#!/usr/bin/env python3
"""Fail the Sky Notes build if a human story link is missing or still routes to JSON."""
from __future__ import annotations
import json, re, sys
from pathlib import Path

year, start_week, end_week = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
checked = 0
empty_states = 0
pages_checked = 0
canonical_week_dir = re.compile(r"^[Ww](\d{1,2})$")

for root in (Path("almanack"), Path("site")):
    year_root = root / str(year)
    if not year_root.exists():
        continue

    for page in year_root.glob("*/index.html"):
        match = canonical_week_dir.fullmatch(page.parent.name)
        if not match:
            continue

        week = int(match.group(1))
        if not start_week <= week <= end_week:
            continue

        text = page.read_text(encoding="utf-8")
        pages_checked += 1
        page_deep_sky = 0
        for fixed_id in dict.fromkeys(re.findall(r'data-fixed-object-id="(\d+)"', text)):
            descriptor = Path("almanack/descriptors") / f"{fixed_id}.json"
            if not descriptor.exists():
                continue
            record = json.loads(descriptor.read_text(encoding="utf-8"))
            if record.get("type") != "deep-sky-object":
                continue
            human = (record.get("representation") or {}).get("human")
            if not human:
                raise SystemExit(f"{page}: deep-sky descriptor {fixed_id} has no human representation")
            target = Path(human.lstrip("/"))
            if not target.exists():
                raise SystemExit(f"{page}: missing human target {human}")
            if f'href="/almanack/descriptors/{fixed_id}.json"' in text:
                raise SystemExit(f"{page}: reader-facing link still points to JSON for {fixed_id}")
            reader_human = "../../../" + human.lstrip("/") if human.startswith("/stories/") else human
            if f'href="{reader_human}"' not in text:
                raise SystemExit(f"{page}: missing reader-facing link {reader_human}")
            checked += 1
            page_deep_sky += 1

        if page_deep_sky == 0:
            empty_state = "No deep-sky objects are featured this week."
            if empty_state not in text:
                raise SystemExit(f"{page}: no deep-sky objects found and reader-facing empty state is missing")
            empty_states += 1

if pages_checked == 0:
    raise SystemExit("No weekly Sky Notes pages were verified")
print(f"Verified {checked} human deep-sky link(s) and {empty_states} explicit no-deep-sky state(s), descriptor mappings, and materialized targets")
