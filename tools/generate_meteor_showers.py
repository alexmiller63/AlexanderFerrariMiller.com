#!/usr/bin/env python3
"""Offline meteor shower catalog and 2025-2027 annual-event generator.

Inputs: curated, source-verifiable peak dates and local observing assessments.
No predicted rate or moonlight is fabricated. Unverified events are never promoted.
Outputs: JSON registry, calendar and sky-notes feeds, HTML event pages and a card.
"""
import argparse
import datetime as dt
import html
import json
from pathlib import Path

YEARS = (2025, 2026, 2027)
# IAU shower numbers are permanent; peak dates below are approximate calendar anchors,
# NOT predictions of the precise UTC maximum. Verify yearly predictions before promotion.
SHOWERS = [
    ("QUA", 10, "Quadrantids", 1, 3, 120),
    ("LYR", 6, "April Lyrids", 4, 22, 18),
    ("ETA", 31, "eta Aquariids", 5, 6, 50),
    ("SDA", 5, "Southern delta Aquariids", 7, 30, 25),
    ("PER", 7, "Perseids", 8, 12, 100),
    ("ORI", 8, "Orionids", 10, 21, 20),
    ("LEO", 13, "Leonids", 11, 17, 15),
    ("GEM", 4, "Geminids", 12, 14, 120),
    ("URS", 15, "Ursids", 12, 22, 10),
]
SOURCE = "https://www.imo.net/calendar/"

def week_start(date):
    return (date - dt.timedelta(days=date.weekday())).isoformat()

def build(assessments):
    registry, events, calendar, notes = [], [], [], {}
    for code, number, name, month, day, zhr in SHOWERS:
        registry.append({"id": f"IAU-{number:04d}", "code": code, "name": name,
                         "typical_peak_month": month, "typical_peak_day": day,
                         "reference_zhr_ideal": zhr, "source": SOURCE})
        for year in YEARS:
            anchor = dt.date(year, month, day)
            event_id = f"{code}-{year}"
            review = assessments.get(event_id, {})
            # Explicit annual verification AND positive local observing assessment required.
            verified = review.get("annual_peak_verified") is True
            recommended = verified and review.get("naked_eye_quality") == "worthwhile"
            peak = review.get("peak_date") if verified else None
            if peak:
                actual = dt.date.fromisoformat(peak)
                if actual.year != year:
                    raise ValueError(f"{event_id}: peak date outside event year")
            else:
                actual = anchor
            record = {
                "id": event_id, "shower_id": f"IAU-{number:04d}", "name": name,
                "year": year, "approximate_peak_date": anchor.isoformat(),
                "verified_peak_date": peak, "annual_peak_verified": verified,
                "naked_eye_quality": review.get("naked_eye_quality", "unassessed"),
                "moonlight_assessment": review.get("moonlight_assessment"),
                "radiant_visibility": review.get("radiant_visibility"),
                "observing_location": review.get("observing_location"),
                "recommended": recommended, "reference_zhr_ideal": zhr,
                "source": review.get("source", SOURCE),
                "detail_path": f"meteor-showers/{event_id}.html",
                "week_start": week_start(actual),
            }
            events.append(record)
            if recommended:
                calendar.append({"date": actual.isoformat(), "event_id": event_id,
                                 "title": name + " meteor shower",
                                 "detail_path": record["detail_path"]})
                notes.setdefault(record["week_start"], []).append({
                    "event_id": event_id, "name": name,
                    "detail_path": record["detail_path"],
                    "text": f"{name}: favorable naked-eye observing opportunity. "
                            "Consult the event page for location-specific guidance."})
    assert len({r["id"] for r in events}) == len(events)
    return registry, events, calendar, notes

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--assessments", type=Path, help="Reviewed annual assessments JSON object")
    p.add_argument("--output", type=Path, default=Path("generated/meteor-showers"))
    args = p.parse_args()
    reviews = json.loads(args.assessments.read_text(encoding="utf-8")) if args.assessments else {}
    if not isinstance(reviews, dict):
        p.error("assessments must be a JSON object keyed by event ID")
    registry, events, calendar, notes = build(reviews)
    root = args.output
    dump(root / "shower-registry.json", registry)
    dump(root / "annual-events-2025-2027.json", events)
    dump(root / "calendar-events.json", calendar)
    dump(root / "sky-notes-by-week.json", notes)
    dump(root / "meteor-card.json", {
        "title": "Meteor Showers", "years": list(YEARS),
        "events": [e for e in events if e["recommended"]]})
    for e in events:
        status = "Recommended for naked-eye observing" if e["recommended"] else "Not recommended until annual observing conditions are verified"
        name = html.escape(e["name"])
        body = (f"<!doctype html><html lang='en'><meta charset='utf-8'>"
                f"<title>{name} — {e['year']}</title><main><h1>{name} — {e['year']}</h1>"
                f"<p>{html.escape(status)}</p><p>IAU shower: {e['shower_id']}</p>"
                f"<p>Typical peak near {e['approximate_peak_date']}; not a verified annual prediction.</p>"
                f"<p>Ideal reference ZHR: {e['reference_zhr_ideal']} (not an observed hourly rate).</p>"
                f"<p>Source: <a href='{SOURCE}'>IMO meteor shower calendar</a></p></main></html>\n")
        path = root / e["detail_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    print(f"Generated {len(registry)} catalog showers, {len(events)} annual pages, "
          f"{len(calendar)} recommended calendar entries.")
    print("Unreviewed annual events remain excluded from Calendar, Sky Notes and card.")

if __name__ == "__main__":
    main()
