#!/usr/bin/env python3
"""Fail the Sky Notes build if a human story link is missing or still routes to JSON."""
from __future__ import annotations
import json, re, sys
from pathlib import Path

year, start_week, end_week = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
checked = 0
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
            if f'href="{human}"' not in text:
                raise SystemExit(f"{page}: missing reader-facing link {human}")
            checked += 1

if checked == 0:
    raise SystemExit("No human deep-sky links were verified")
print(f"Verified {checked} human deep-sky link(s), descriptor mappings, and materialized targets")
