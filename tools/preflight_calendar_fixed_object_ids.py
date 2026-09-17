#!/usr/bin/env python3
"""Audit Calendar fixed-object IDs as one batch before downstream generation.

Current IDs pass. Retired IDs are resolved through the human-reviewed merge table.
Unknown IDs and broken/cyclic merge chains are collected and reported together.
The tool is intentionally read-only: canonical Calendar sources should be regenerated or
repaired by their owning pipeline rather than silently mutated here.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBJECTS = ROOT / "database" / "fixed-objects.json"
MERGES = ROOT / "database" / "fixed-object-id-merges.json"
CALENDAR_ROOT = ROOT / "almanack"
ID_RE = re.compile(r'\bdata-fixed-object-id="(\d+)"')


def load_current_ids() -> set[int]:
    payload = json.loads(OBJECTS.read_text(encoding="utf-8"))
    return {int(obj["fixed_object_id"]) for obj in payload.get("fixed_objects") or []}


def load_merges() -> dict[int, int]:
    payload = json.loads(MERGES.read_text(encoding="utf-8"))
    return {
        int(item["retired_fixed_object_id"]): int(item["surviving_fixed_object_id"])
        for item in payload.get("merges") or []
    }


def resolve(fixed_id: int, current: set[int], merges: dict[int, int]) -> tuple[int | None, list[int], str | None]:
    chain = [fixed_id]
    seen = {fixed_id}
    value = fixed_id
    while value not in current:
        if value not in merges:
            return None, chain, "unknown"
        value = merges[value]
        chain.append(value)
        if value in seen:
            return None, chain, "cycle"
        seen.add(value)
    return value, chain, None


def calendar_pages() -> list[Path]:
    return sorted(CALENDAR_ROOT.glob("[0-9][0-9][0-9][0-9]/W[0-9][0-9]/index.html"))


def main() -> None:
    current = load_current_ids()
    merges = load_merges()
    retired: dict[tuple[int, int], list[str]] = {}
    failures: dict[tuple[int, tuple[int, ...], str], list[str]] = {}
    refs = 0

    for path in calendar_pages():
        rel = str(path.relative_to(ROOT))
        ids = [int(raw) for raw in ID_RE.findall(path.read_text(encoding="utf-8"))]
        refs += len(ids)
        for fixed_id in ids:
            survivor, chain, error = resolve(fixed_id, current, merges)
            if error:
                failures.setdefault((fixed_id, tuple(chain), error), []).append(rel)
            elif survivor != fixed_id:
                retired.setdefault((fixed_id, survivor), []).append(rel)

    print(f"Calendar fixed-object preflight: {len(calendar_pages())} pages, {refs} references")
    if retired:
        print(f"Retired references with documented survivors: {len(retired)}")
        for (old, new), paths in sorted(retired.items()):
            print(f"  {old} -> {new}: {len(paths)} page(s); first {paths[0]}")

    if failures:
        print(f"ERROR: {len(failures)} unresolved fixed-object identity class(es):", file=sys.stderr)
        for (fixed_id, chain, error), paths in sorted(failures.items()):
            route = " -> ".join(map(str, chain))
            print(f"  {fixed_id}: {error}; chain {route}; {len(paths)} page(s); first {paths[0]}", file=sys.stderr)
        raise SystemExit(1)

    if retired:
        print("ERROR: Calendar contains retired fixed_object_id values. Regenerate/repair canonical Calendar IDs in one batch using the mappings above.", file=sys.stderr)
        raise SystemExit(1)

    print("PASS: every Calendar fixed_object_id is current and resolves to database/fixed-objects.json")


if __name__ == "__main__":
    main()
