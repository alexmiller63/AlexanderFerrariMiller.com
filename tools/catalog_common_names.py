#!/usr/bin/env python3
"""Common-name reconciliation for Messier, Caldwell, and Finest NGC.

Catalog/source identifiers are not reader-facing common names.  Prefer an
attested common name when one is available; otherwise return an empty string.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"

_ALT_ID = re.compile(
    r"^(?:NGC|IC|M|C|OCL|COLLINDER|CR|ARP|MCG|UGC|PGC|PN\s*G|SH\s*2|SH2|VDB|LBN|LDN)\b",
    re.I,
)


def reader_name(value: str | None) -> str:
    """Return value only when it reads as a common name, not another catalog ID."""
    name = (value or "").strip()
    if not name or _ALT_ID.match(name):
        return ""
    return name


def messier_names() -> dict[str, str]:
    """First NASA-attested name is the preferred Almanack display name."""
    path = SRC / "messier-common-names-nasa.yaml"
    out: dict[str, str] = {}
    active = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip() == "names:":
            active = True
            continue
        if not active:
            continue
        m = re.match(r"\s+(M\d{1,3}):\s*\[(.*)\]\s*$", raw)
        if not m:
            continue
        names = next(csv.reader([m.group(2)], skipinitialspace=True))
        if names:
            out[m.group(1).upper()] = names[0].strip()
    return out


def finest_names_by_catalog() -> dict[str, str]:
    """Reader-facing names from the RASC Finest NGC source, keyed by NGC/IC ID."""
    path = SRC / "finest-ngc-catalog.csv"
    out: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = reader_name(row.get("name"))
            if name:
                out.setdefault(row["catalog"].strip().upper(), name)
    return out


def preferred_messier_name(designation: str, existing: str | None = None) -> str:
    return messier_names().get(designation.upper()) or reader_name(existing)


def preferred_deep_sky_name(catalog: str, existing: str | None = None) -> str:
    """Keep a real catalog-supplied common name; fill blanks from RASC overlap data."""
    return reader_name(existing) or finest_names_by_catalog().get(catalog.strip().upper(), "")
