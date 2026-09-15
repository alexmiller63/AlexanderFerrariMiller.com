#!/usr/bin/env python3
"""Audit exact duplicate Bayer designations in the expanded star catalog.

A repeated exact Bayer designation can be legitimate when the source catalog
contains multiple physical components of one naked-eye system, but the Almanack
must treat the system as one observer-facing placement. Component systems that
already carry Bayer suffixes (for example alpha1/alpha2) are distinct keys and
are not duplicates here.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
CATALOG = ROOT / "expanded-bayer-stars.csv"

# Known exact system-level duplicates in the current source catalog.
# Both represent multiple physical components sharing one Bayer designation.
EXPECTED = {
    ("Alp", "Com"): "Diadem / alpha Com component pair",
    ("Alp", "Gem"): "Castor / Castor B component pair",
}


def main() -> None:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    with CATALOG.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = ((row.get("bayer_code") or "").strip(), (row.get("con") or "").strip())
            groups[key].append(row)

    duplicates = {key: rows for key, rows in groups.items() if len(rows) > 1}

    print(f"Found {len(duplicates)} exact duplicate Bayer designation groups.")
    for key in sorted(duplicates):
        rows = duplicates[key]
        names = [((r.get("proper") or "").strip() or "(unnamed component)") for r in rows]
        hrs = [((r.get("hr") or "").strip() or "?") for r in rows]
        status = "expected" if key in EXPECTED else "UNEXPECTED"
        note = EXPECTED.get(key, "")
        print(f"- {key[0]} {key[1]}: {len(rows)} rows; {', '.join(names)}; HR {', '.join(hrs)}; {status}{'; ' + note if note else ''}")

    expected_keys = set(EXPECTED)
    actual_keys = set(duplicates)
    unexpected = actual_keys - expected_keys
    missing = expected_keys - actual_keys

    if unexpected or missing:
        if unexpected:
            print("FAIL: unexpected exact duplicate designation(s):")
            for code, con in sorted(unexpected):
                print(f"- {code} {con}")
        if missing:
            print("FAIL: expected duplicate designation(s) disappeared; review source normalization:")
            for code, con in sorted(missing):
                print(f"- {code} {con}")
        raise SystemExit(1)

    print("PASS: exact duplicate Bayer designations are limited to the two known component systems: alpha Com and alpha Gem.")


if __name__ == "__main__":
    main()
