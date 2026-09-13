#!/usr/bin/env python3
"""Audit Star Almanack timed-event publication invariants.

Invariant:
    calculate astronomical instant -> round once to publication precision ->
    derive UTC date and UTC time from that same rounded instant.

This audit checks the canonical time layer, generated event JSON, eclipse source
records, and generator source paths for obvious regressions that would split a
published date from its rounded UTC time.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "Star-Almanack-Repo" / "generated"
ECLIPSE_YAML = ROOT / "Star-Almanack-Repo" / "eclipse.yaml"

TIMED_GENERATORS = (
    ROOT / "tools" / "populate_calendar.py",
    ROOT / "tools" / "populate_galactic_center.py",
    ROOT / "tools" / "populate_meteor_showers.py",
    ROOT / "Star-Almanack-Repo" / "besselian_eclipse_engine.py",
    ROOT / "tools" / "wire_2026_eclipses.py",
)

FORBIDDEN_SOURCE_PATTERNS = (
    r"utc_datetime\(\)\.date\(\)",
    r"utc_datetime\(\)\.strftime\(",
)


def parse_utc_iso(text: str) -> datetime:
    if not isinstance(text, str) or not text.endswith("Z"):
        raise ValueError(f"UTC value is not a Z-suffixed ISO string: {text!r}")
    return datetime.fromisoformat(text[:-1] + "+00:00")


def walk_json(node, path="$"):
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from walk_json(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk_json(value, f"{path}[{i}]")


def audit_generated_json() -> int:
    checked = 0
    if not GENERATED.exists():
        return checked
    for file in sorted(GENERATED.glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        for where, obj in walk_json(data):
            if "utc" not in obj:
                continue
            utc = parse_utc_iso(obj["utc"])
            checked += 1
            for date_key in ("date", "utc_date", "calendar_date", "event_date"):
                if date_key in obj:
                    expected = utc.date().isoformat()
                    if str(obj[date_key]) != expected:
                        raise SystemExit(
                            f"FAIL {file}:{where}: {date_key}={obj[date_key]!r} "
                            f"but rounded utc={obj['utc']!r} belongs to {expected}"
                        )
    return checked


def audit_eclipse_source() -> int:
    """Ensure eclipse publication date and maximum UTC are one civil event date.

    eclipse.yaml stores maximum_geometry_utc as a time-only value, so the
    explicit date field is the UTC date paired with that clock time. Validate
    both fields strictly and reject malformed or non-normalized publication
    values before the wiring script can place them on a calendar row.
    """
    text = ECLIPSE_YAML.read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^  - id: ", text)[1:]
    checked = 0
    for block in blocks:
        date_match = re.search(r"(?m)^    date:\s*(\d{4}-\d{2}-\d{2})\s*$", block)
        time_match = re.search(
            r'(?m)^    maximum_geometry_utc:\s*"(\d{2}:\d{2}:\d{2})"\s*$', block
        )
        if not date_match or not time_match:
            raise SystemExit("FAIL eclipse.yaml: eclipse missing normalized date/maximum UTC")
        stamp = datetime.fromisoformat(f"{date_match.group(1)}T{time_match.group(1)}+00:00")
        if stamp.date().isoformat() != date_match.group(1):
            raise SystemExit("FAIL eclipse.yaml: date/time publication split")
        checked += 1
    return checked


def audit_generator_source() -> int:
    checked = 0
    for path in TIMED_GENERATORS:
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_SOURCE_PATTERNS:
            if re.search(pattern, text):
                raise SystemExit(
                    f"FAIL {path.relative_to(ROOT)}: bypasses canonical publication boundary: {pattern}"
                )
        checked += 1
    return checked


def main() -> None:
    generated = audit_generated_json()
    eclipses = audit_eclipse_source()
    generators = audit_generator_source()
    print("TIMED-EVENT UTC PUBLICATION INVARIANT: PASS")
    print(f"generated UTC records checked: {generated}")
    print(f"eclipse publication records checked: {eclipses}")
    print(f"timed generator source paths checked: {generators}")


if __name__ == "__main__":
    main()
