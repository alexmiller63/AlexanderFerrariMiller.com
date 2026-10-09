"""Permanent object identities; display names are accepted only at source ingestion."""
from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=None)
def identity_registry() -> dict:
    return json.loads((ROOT / "descriptor-identities.json").read_text(encoding="utf-8"))


def asterism_identity(identifier: int | str) -> dict:
    records = identity_registry()["asterisms"]
    matches = [r for r in records if str(r["id"]) == str(identifier)
               or r["geometry_key"] == identifier]
    if len(matches) != 1:
        raise RuntimeError(f"Unknown or ambiguous asterism identity: {identifier!r}")
    return dict(matches[0])


@lru_cache(maxsize=None)
def fixed_object_ids() -> frozenset[int]:
    data = json.loads((ROOT / "database/fixed-objects.json").read_text(encoding="utf-8"))
    return frozenset(o["fixed_object_id"] for o in data["fixed_objects"])


@lru_cache(maxsize=None)
def hip_identities() -> dict[str, int]:
    data = json.loads((ROOT / "database/fixed-object-registry.json").read_text(encoding="utf-8"))
    result = {}
    for obj in data["fixed_objects"]:
        if obj.get("status") != "active":
            continue
        for ref in obj.get("identifiers", []):
            if str(ref.get("namespace", "")).lower() == "hip":
                hip = str(ref["value"])
                if hip in result and result[hip] != obj["fixed_object_id"]:
                    raise RuntimeError(f"Ambiguous HIP identity: {hip}")
                result[hip] = obj["fixed_object_id"]
    return result


def require_fixed_object_id(identifier: int) -> int:
    if type(identifier) is not int or identifier not in fixed_object_ids():
        raise RuntimeError(f"Unknown permanent fixed_object_id: {identifier!r}")
    return identifier


def fixed_id_for_hip(hip: str) -> int:
    identifier = hip_identities().get(str(hip).strip())
    return require_fixed_object_id(identifier)


def catalog_object_metadata() -> dict[int, dict]:
    """Join catalog display fields through explicit, permanent identifiers."""
    registry = json.loads((ROOT / "database/fixed-object-registry.json").read_text())
    aliases = {}
    for obj in registry["fixed_objects"]:
        if obj.get("status") != "active":
            continue
        for ident in obj.get("identifiers", []):
            key = (ident["namespace"].lower(), str(ident["value"]).lower())
            if key in aliases and aliases[key] != obj["fixed_object_id"]:
                raise RuntimeError(f"Ambiguous catalog identity {key}")
            aliases[key] = obj["fixed_object_id"]
    result = {}
    for filename, namespace, field in (
        ("caldwell-catalog.csv", "caldwell", "caldwell"),
        ("finest-ngc-catalog.csv", "finest_ngc", "finest_ngc"),
        ("special-star-catalog.csv", "hip", "hip"),
    ):
        with (ROOT / filename).open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                key = (namespace, str(row.get(field) or "").strip().lower())
                fid = aliases.get(key)
                if fid is None:
                    continue
                designation = str(row.get("catalog") or row.get("caldwell") or row.get("finest_ngc") or "").strip()
                name = str(row.get("name") or "").strip() or designation
                record = result.setdefault(fid, {})
                if name:
                    record.setdefault("name", name)
                if row.get("con"):
                    record.setdefault("constellation", row["con"])
                if namespace == "hip":
                    record["object_type_family"] = "star"
    return result


@lru_cache(maxsize=None)
def resolve_source_name(name: str, constellation: str | None = None) -> int:
    """Resolve legacy source labels once; never invent an identity from a name."""
    wanted = name.split(",", 1)[0].strip().casefold()
    matches = set()
    data = json.loads((ROOT / "database/fixed-objects.json").read_text(encoding="utf-8"))
    for obj in data["fixed_objects"]:
        for src in obj.get("source_records", []):
            facts = src.get("facts") or {}
            if constellation and facts.get("constellation") not in (None, "", constellation):
                continue
            if str(facts.get("name") or "").split(",", 1)[0].strip().casefold() == wanted:
                matches.add(obj["fixed_object_id"])
    for filename in ("bright-stars-2mag.csv", "expanded-bayer-stars.csv"):
        with (ROOT / filename).open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if constellation and row.get("con") != constellation:
                    continue
                if str(row.get("proper") or "").strip().casefold() == wanted:
                    fid = hip_identities().get(str(row.get("hip") or "").strip())
                    if fid is not None:
                        matches.add(fid)
    if len(matches) != 1:
        raise RuntimeError(f"Source label {name!r} ({constellation}) resolves to {sorted(matches)}; expected one permanent ID")
    return require_fixed_object_id(matches.pop())
