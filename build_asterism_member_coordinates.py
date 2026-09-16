#!/usr/bin/env python3
"""Build asterism member stellar data from permanent Star Almanack identity.

Identity policy:
  1. An asterism member label identifies a permanent fixed_object_id through
     database/fixed-object-registry.json.
  2. External catalog identifiers attached to that fixed object are used only
     to retrieve astronomical facts from the pinned HYG v4.1 source.
  3. Human-readable names are display/provenance data, never computational
     identity.

There are deliberately no per-object resolver overrides and no network name
resolution. An unresolved identity is a database integrity error and fails the
build loudly.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_ASTERISMS = ROOT / "asterisms-core-25.yaml"
DEFAULT_REGISTRY = ROOT / "database" / "fixed-object-registry.json"
DEFAULT_OUTPUT = ROOT / "asterism-member-coordinates.csv"
HYG_PIN = "astronexus/HYG-Database@3bf37f4b2d5460e1278286320d1d62fab9b493c1:hyg/CURRENT/hygdata_v41.csv"


def load_asterisms(path: Path):
    entries = []
    current = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("  - name: "):
            if current is not None:
                entries.append(current)
            current = {"name": raw.split(":", 1)[1].strip()}
        elif current is not None and raw.startswith("    status: "):
            current["status"] = raw.split(":", 1)[1].strip()
        elif current is not None and raw.startswith("    members: ["):
            body = raw.split("[", 1)[1].rsplit("]", 1)[0]
            current["members"] = [item.strip() for item in body.split(",") if item.strip()]
    if current is not None:
        entries.append(current)
    if not entries:
        raise RuntimeError(f"No asterisms parsed from {path}")
    for entry in entries:
        if entry.get("status") != "resolved" or not entry.get("members"):
            raise RuntimeError(f"Incomplete asterism entry: {entry}")
    return entries


def load_registry(path: Path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    by_member = {}
    for record in doc.get("fixed_objects") or []:
        if record.get("status") != "active":
            continue
        for ident in record.get("identifiers") or []:
            if ident.get("namespace") != "asterism_member_label":
                continue
            label = str(ident.get("value") or "").strip()
            if not label:
                continue
            prior = by_member.get(label)
            if prior is not None and prior["fixed_object_id"] != record["fixed_object_id"]:
                raise RuntimeError(
                    f"Asterism member label {label!r} maps to multiple fixed_object_id values"
                )
            by_member[label] = record
    return by_member


def load_hyg(path: Path):
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8-sig")))
    required = {"id", "hip", "hd", "hr", "proper", "ra", "dec", "mag"}
    missing = required.difference(rows[0].keys() if rows else set())
    if missing:
        raise RuntimeError(f"HYG input missing columns: {sorted(missing)}")
    indexes = {"hip": {}, "hd": {}, "hr": {}, "hyg": {}}
    for row in rows:
        for field in ("hip", "hd", "hr", "id"):
            value = str(row.get(field) or "").strip()
            if value:
                indexes["hyg" if field == "id" else field][value] = row
    return indexes


def fixed_object_catalog_identity(record):
    identifiers = record.get("identifiers") or []
    for namespace in ("hip", "hd", "hr", "hyg"):
        values = [str(i.get("value") or "").strip() for i in identifiers if i.get("namespace") == namespace]
        values = [v for v in values if v]
        if len(values) > 1:
            raise RuntimeError(
                f"fixed_object_id {record['fixed_object_id']} has multiple {namespace.upper()} identifiers: {values}"
            )
        if values:
            return namespace, values[0]
    raise RuntimeError(
        f"fixed_object_id {record['fixed_object_id']} has no HYG-addressable catalog identifier"
    )


def hyg_identity(namespace: str, value: str) -> str:
    return f"{namespace.upper()} {value}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asterisms", type=Path, default=DEFAULT_ASTERISMS)
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    ap.add_argument("--hyg", type=Path, required=True, help="Pinned HYG v4.1 CSV used as the astronomical fact source")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    catalog = load_asterisms(args.asterisms)
    by_member = load_registry(args.registry)
    hyg = load_hyg(args.hyg)

    out = []
    failures = []
    for asterism in catalog:
        for member in asterism["members"]:
            record = by_member.get(member)
            if record is None:
                failures.append(f"{asterism['name']}: {member}: no active fixed_object_id")
                continue
            fixed_id = record["fixed_object_id"]
            try:
                namespace, value = fixed_object_catalog_identity(record)
            except RuntimeError as exc:
                failures.append(f"{asterism['name']}: {member}: {exc}")
                continue
            hrow = hyg[namespace].get(value)
            if hrow is None:
                failures.append(
                    f"{asterism['name']}: {member}: fixed_object_id {fixed_id} -> "
                    f"{hyg_identity(namespace, value)} absent from pinned HYG"
                )
                continue
            try:
                ra_h = float(hrow["ra"])
                dec_deg = float(hrow["dec"])
                magnitude = float(hrow["mag"])
            except (TypeError, ValueError):
                failures.append(
                    f"{asterism['name']}: {member}: fixed_object_id {fixed_id} has incomplete HYG facts"
                )
                continue

            source_id = hyg_identity(namespace, value)
            resolved = str(hrow.get("proper") or "").strip() or member
            out.append({
                "asterism": asterism["name"],
                "member": member,
                "fixed_object_id": fixed_id,
                "resolved_object": resolved,
                "ra_h": f"{ra_h:.10f}",
                "dec_deg": f"{dec_deg:.10f}",
                "mag": f"{magnitude:g}",
                "coordinate_source": f"Pinned HYG v4.1 ({HYG_PIN})",
                "coordinate_source_id": source_id,
                "magnitude_source": f"Pinned HYG v4.1 ({HYG_PIN})",
                "magnitude_source_id": source_id,
            })

    if failures:
        joined = "\n  - ".join(failures)
        raise SystemExit(
            "Fixed-object identity resolution incomplete; refusing name-based fallback:\n  - " + joined
        )

    fields = [
        "asterism", "member", "fixed_object_id", "resolved_object", "ra_h", "dec_deg", "mag",
        "coordinate_source", "coordinate_source_id", "magnitude_source", "magnitude_source_id",
    ]
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out)

    print(f"Wrote {len(out)} fixed-ID member rows for {len(catalog)} asterisms to {args.output}")
    print("PASS: every asterism member resolved through immutable fixed_object_id; no name resolver used")


if __name__ == "__main__":
    main()
