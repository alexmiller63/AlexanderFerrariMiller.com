#!/usr/bin/env python3
"""Read-only story completion reports for every selected Calendar object."""
from __future__ import annotations

import html
import re
from datetime import date, timedelta
from pathlib import Path

from almanack_calendar import get_event_records
from almanack_paths import week_index
from fixed_object_stories import COLLECTIONS, read_story
from iso_date_range import parse_range_args


def completion_report(page: Path, year: int, week: int) -> dict:
    text = page.read_text(encoding="utf-8")
    monday = date.fromisocalendar(year, week, 1)
    targets = {}
    for offset in range(7):
        day = monday + timedelta(days=offset)
        records = get_event_records(text, day)
        if records is None:
            raise RuntimeError(f"Missing Calendar row {day}: {page}")
        for event in records:
            if event.fixed_object_id is None and event.catalog_target_key is None:
                continue
            identity = ("fixed", event.fixed_object_id) if event.fixed_object_id is not None else ("catalog", event.catalog_target_key)
            label = html.unescape(re.sub(r"<[^>]+>", "", event.html)).split(" — ", 1)[0].strip()
            target = targets.setdefault(identity, {
                "fixed_object_id": event.fixed_object_id,
                "catalog_target_key": event.catalog_target_key,
                "label": label, "status": "pending", "stories": [],
            })
            if event.fixed_object_id is not None and not target["stories"]:
                for collection in sorted(COLLECTIONS):
                    story = read_story(collection, event.fixed_object_id)
                    if story is not None:
                        target["stories"].append({"collection": collection, "status": story.status, "url": story.public_url})
                if any(story["status"] == "complete" for story in target["stories"]):
                    target["status"] = "complete"
            target["reason"] = (
                "verified story" if target["status"] == "complete" else
                "research written; completion review pending" if target["stories"] else
                "permanent identity and researched story needed" if event.fixed_object_id is None else
                "researched story needed"
            )
    entries = list(targets.values())
    pending = [entry for entry in entries if entry["status"] != "complete"]
    return {"week": f"{year}-W{week:02d}", "total": len(entries),
            "complete": len(entries) - len(pending), "pending": pending, "objects": entries}


def print_report(report: dict) -> None:
    print(f"Story completion {report['week']}: {report['complete']}/{report['total']} complete; {len(report['pending'])} pending")
    for entry in report["pending"]:
        identity = entry["fixed_object_id"] if entry["fixed_object_id"] is not None else entry["catalog_target_key"]
        print(f"  PENDING {identity}: {entry['label']} ({entry['reason']})")


def main() -> None:
    _, _, weeks = parse_range_args("Report researched-story completion by ISO week")
    for item in weeks:
        print_report(completion_report(week_index(item.year, item.week), item.year, item.week))


if __name__ == "__main__":
    main()
