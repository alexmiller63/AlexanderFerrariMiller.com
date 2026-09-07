#!/usr/bin/env python3
"""Add major 2026 meteor-shower maxima to weekly calendar event cells."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EVENTS = {
    "Jan 03, 2026": "☄ Quadrantids peak",
    "Apr 22, 2026": "☄ Lyrids peak",
    "May 06, 2026": "☄ η-Aquariids peak",
    "Jul 31, 2026": "☄ Southern δ-Aquariids peak<br>☄ α-Capricornids peak",
    "Aug 13, 2026": "☄ Perseids peak",
    "Oct 21, 2026": "☄ Orionids peak",
    "Nov 17, 2026": "☄ Leonids peak",
    "Dec 14, 2026": "☄ Geminids peak",
    "Dec 22, 2026": "☄ Ursids peak",
}

for path in sorted((ROOT / "almanack" / "2026").glob("W??/index.html")):
    text = path.read_text(encoding="utf-8")
    original = text
    for date_text, event in EVENTS.items():
        # Match only the calendar row for this civil date, then prepend the
        # shower maximum to its Events cell. Idempotent on repeated runs.
        pattern = re.compile(rf'(<tr><td>[^<]*{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)')
        m = pattern.search(text)
        if not m or event.split("<br>")[0] in m.group(2):
            continue
        existing = m.group(2)
        combined = event if existing == "—" else event + "<br>" + existing
        text = text[:m.start()] + m.group(1) + combined + m.group(3) + text[m.end():]
    if text != original:
        path.write_text(text, encoding="utf-8")
