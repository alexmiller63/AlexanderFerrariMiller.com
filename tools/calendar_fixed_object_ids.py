#!/usr/bin/env python3
"""Attach permanent fixed_object_id metadata to Calendar event cells.

Visible Calendar wording is presentation.  Downstream generators must use the
stable database identity carried by ``data-fixed-object-id`` rather than
reverse-matching display names.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database" / "fixed-objects.json"
EVENT_RE = re.compile(r'(<div\b)(?P<attrs>[^>]*\bclass="[^"]*\bevent-cell\b[^"]*"[^>]*>)(?P<body>.*?)</div>', re.S)


def identity_index() -> tuple[dict[str, int], dict[str, int]]:
    data = json.loads(DB.read_text(encoding="utf-8"))
    names: dict[str, int] = {}
    messier: dict[str, int] = {}
    for obj in data["fixed_objects"]:
        fixed_id = int(obj["fixed_object_id"])
        for record in obj.get("source_records", []):
            facts = record.get("facts", {})
            for key in ("name", "proper"):
                value = facts.get(key)
                if value:
                    names.setdefault(str(value).strip().casefold(), fixed_id)
            source_key = str(record.get("source_key", "")).strip().upper()
            if re.fullmatch(r"M(?:110|10\d|[1-9]\d?)", source_key):
                messier.setdefault(source_key, fixed_id)
    return names, messier


def plain(fragment: str) -> str:
    value = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def resolve(body: str, names: dict[str, int], messier: dict[str, int]) -> int | None:
    text = plain(body)
    m = re.search(r"(?<![A-Za-z0-9])M(?:110|10\d|[1-9]\d?)(?!\d)", text, re.I)
    if m:
        found = messier.get(m.group(0).upper())
        if found is not None:
            return found
    folded = text.casefold()
    hits = [(len(name), fixed_id) for name, fixed_id in names.items()
            if re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", folded)]
    if not hits:
        return None
    hits.sort(reverse=True)
    return hits[0][1]


def patch_text(text: str) -> tuple[str, int]:
    names, messier = identity_index()
    count = 0
    def repl(match: re.Match[str]) -> str:
        nonlocal count
        attrs = match.group("attrs")
        body = match.group("body")
        fixed_id = resolve(body, names, messier)
        attrs = re.sub(r'\s+data-fixed-object-id="[^"]*"', '', attrs)
        if fixed_id is not None:
            attrs = attrs[:-1] + f' data-fixed-object-id="{fixed_id}">'
            count += 1
        return match.group(1) + attrs + body + "</div>"
    return EVENT_RE.sub(repl, text), count


def patch_file(path: Path) -> int:
    old = path.read_text(encoding="utf-8")
    new, count = patch_text(old)
    if new != old:
        path.write_text(new, encoding="utf-8")
    return count
