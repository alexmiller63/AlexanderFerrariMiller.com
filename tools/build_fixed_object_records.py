#!/usr/bin/env python3
"""Build normalized physical fixed-object records keyed only by permanent fixed_object_id.

The identity audit already contains the reconciled source candidates and their
astronomical fields. This builder joins those candidates to the immutable
registry through source_refs, preserving source data without making names or
catalog spellings part of identity.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "generated" / "fixed-object-identity-audit.json"
REGISTRY_PATH = ROOT / "database" / "fixed-object-registry.json"
OUT_PATH = ROOT / "database" / "fixed-objects.json"

IDENTITY_ONLY_KEYS = {"candidate_id", "identifiers", "source", "source_key"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    audit = load(AUDIT_PATH)
    registry = load(REGISTRY_PATH)
    candidates = audit.get("candidates") or []
    by_source = {}
    for candidate in candidates:
        key = (str(candidate["source"]), str(candidate["source_key"]))
        if key in by_source:
            raise SystemExit(f"Duplicate audit source reference: {key}")
        by_source[key] = candidate

    records = []
    unresolved = []
    for identity in registry.get("fixed_objects") or []:
        if identity.get("status") != "active":
            continue
        source_records = []
        for ref in identity.get("source_refs") or []:
            key = (str(ref["source"]), str(ref["source_key"]))
            candidate = by_source.get(key)
            if candidate is None:
                unresolved.append((identity["fixed_object_id"], key))
                continue
            facts = {k: v for k, v in candidate.items() if k not in IDENTITY_ONLY_KEYS}
            source_records.append({
                "source": ref["source"],
                "source_key": ref["source_key"],
                "facts": facts,
            })
        records.append({
            "fixed_object_id": identity["fixed_object_id"],
            "source_records": source_records,
        })

    if unresolved:
        text = "\n".join(f"fixed_object_id {fid}: {key}" for fid, key in unresolved)
        raise SystemExit("Registry source_refs missing from audit; build aborted:\n" + text)

    ids = [r["fixed_object_id"] for r in records]
    if len(ids) != len(set(ids)):
        raise SystemExit("Duplicate fixed_object_id in normalized records.")
    if len(records) != registry.get("active_object_count"):
        raise SystemExit("Normalized record count does not match active registry count.")

    result = {
        "schema_version": 1,
        "purpose": "Normalized astronomical source records for physical fixed objects, keyed by immutable fixed_object_id.",
        "identity_registry": "database/fixed-object-registry.json",
        "source_audit": "generated/fixed-object-identity-audit.json",
        "fixed_object_count": len(records),
        "fixed_objects": records,
    }
    OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH.relative_to(ROOT)} with {len(records)} fixed objects.")


if __name__ == "__main__":
    main()
