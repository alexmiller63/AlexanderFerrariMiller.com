#!/usr/bin/env python3
"""Insert verified, dated planetary phenomena without rebuilding weekly charts.

Input JSON: {"events":[{"utc":"2026-01-10T08:42:00Z",
"kind":"opposition","planet":"Jupiter","description":"Visible all night.",
"source_url":"https://..."}]}. An empty list is valid but publishes nothing.
Only vetted event records are accepted; this script does not infer event instants
from weekly planetary snapshots.
"""
import argparse
import datetime as dt
import html
import json
import re
from pathlib import Path

from almanack_calendar import CalendarEvent, get_event_records, set_events
from almanack_paths import week_index

ROOT = Path(__file__).resolve().parents[1]
KINDS = {"opposition", "greatest elongation", "maximum brilliance",
         "conjunction", "retrograde station", "direct station",
         "lunar occultation", "solar transit"}
PLANETS = {"Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"}
MARKER = 'data-planetary-event-id="'
TIME = re.compile(r"\b(\d{2}):(\d{2})(?::(\d{2}))? UTC\b")

def load_events(path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    events = {}
    seen = set()
    for item in payload["events"]:
        instant = dt.datetime.fromisoformat(item["utc"].replace("Z", "+00:00"))
        if instant.tzinfo is None or instant.utcoffset() != dt.timedelta(0):
            raise ValueError("Planetary event timestamps must be UTC")
        kind, planet = item["kind"], item["planet"]
        if kind not in KINDS or planet not in PLANETS:
            raise ValueError(f"Unsupported planetary event: {kind}, {planet}")
        description = item["description"].strip()
        if not description:
            raise ValueError("Observing description is required")
        key = f"{instant:%Y%m%dT%H%M%SZ}-{planet.lower().replace(' ','-')}-{kind.replace(' ','-')}"
        if key in seen:
            raise ValueError(f"Duplicate planetary event: {key}")
        seen.add(key)
        url = item.get("source_url", "")
        if url and not url.startswith("https://"):
            raise ValueError("Source links must be HTTPS")
        label = f"{planet} {kind} — {instant:%H:%M:%S} UTC · {description}"
        markup = f'<span {MARKER}{key}">{html.escape(label)}</span>'
        events.setdefault(instant.date(), []).append((instant, key, CalendarEvent(markup)))
    return events

def update(events, dry_run=False, only_week=None):
    changed = []
    weeks = sorted({(d.isocalendar().year, d.isocalendar().week) for d in events})
    if only_week is not None:
        weeks = [w for w in weeks if w == only_week]
    for year, week in weeks:
        path = week_index(year, week)
        if not path.is_file():
            raise RuntimeError(f"Missing populated weekly page: {path}")
        before = path.read_text(encoding="utf-8")
        text = before
        monday = dt.date.fromisocalendar(year, week, 1)
        for offset in range(7):
            day = monday + dt.timedelta(days=offset)
            existing = get_event_records(text, day)
            if existing is None:
                raise RuntimeError(f"Missing calendar date {day} in {path}")
            # Replace only records previously produced by this generator.
            kept = [e for e in existing if MARKER not in e.html]
            additions = [record for _, _, record in sorted(events.get(day, []))]
            # Preserve existing entries and order planetary events by UTC.
            merged = kept + additions
            text, found = set_events(text, day, merged)
            if not found:
                raise RuntimeError(f"Unable to write calendar date {day}")
        if text != before:
            changed.append(path)
            if not dry_run:
                path.write_text(text, encoding="utf-8")
    return changed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, default=ROOT / "data" / "planetary-events.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--week", help="Restrict changes to an ISO week, e.g. 2026-W02")
    args = parser.parse_args()
    only_week = None
    if args.week:
        match = re.fullmatch(r"(\d{4})-W(\d{2})", args.week)
        if not match:
            parser.error("--week must be YYYY-Www")
        only_week = (int(match.group(1)), int(match.group(2)))
        try:
            dt.date.fromisocalendar(*only_week, 1)
        except ValueError as exc:
            parser.error(str(exc))
    events = load_events(args.events)
    changed = update(events, args.dry_run, only_week)
    for path in changed:
        print(f"{'Would update' if args.dry_run else 'Updated'} {path.relative_to(ROOT)}")
    print(f"{len(changed)} affected weekly pages; {sum(map(len, events.values()))} verified events")

if __name__ == "__main__":
    main()
