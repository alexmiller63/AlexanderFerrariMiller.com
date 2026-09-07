#!/usr/bin/env python3
"""Build the resolved coordinate cross-match for the 25 core asterisms.

Policy:
  1. Use Star Almanack's expanded Bayer catalog wherever it contains the member.
  2. Apply explicit ambiguity overrides from asterism-coordinate-resolution.yaml.
  3. Resolve only the remaining objects through CDS Sesame/SIMBAD.

The output is a pinned CSV consumed by compute_asterism_geometry_2026.py.
J2000/ICRS decimal coordinates are written with their source and resolved object
name so every geometry vertex remains inspectable.
"""
from __future__ import annotations

import argparse
import csv
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
DEFAULT_ASTERISMS = ROOT / "asterisms-core-25.yaml"
DEFAULT_OVERRIDES = ROOT / "asterism-coordinate-resolution.yaml"
DEFAULT_BAYER = ROOT / "expanded-bayer-stars.csv"
DEFAULT_OUTPUT = ROOT / "asterism-member-coordinates.csv"
SESAME = "https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV?{}"

GREEK_TO_CODE = {
    "Alpha": "Alp", "Beta": "Bet", "Gamma": "Gam", "Delta": "Del",
    "Epsilon": "Eps", "Zeta": "Zet", "Eta": "Eta", "Theta": "The",
    "Iota": "Iot", "Kappa": "Kap", "Lambda": "Lam", "Mu": "Mu",
    "Nu": "Nu", "Xi": "Xi", "Omicron": "Omi", "Pi": "Pi", "Rho": "Rho",
    "Sigma": "Sig", "Tau": "Tau", "Upsilon": "Ups", "Phi": "Phi",
    "Chi": "Chi", "Psi": "Psi", "Omega": "Ome",
}

CONSTELLATION_TO_ABBR = {
    "Aquarii": "Aqr", "Bootis": "Boo", "Canum Venaticorum": "CVn",
    "Cassiopeiae": "Cas", "Centauri": "Cen", "Ceti": "Cet", "Crucis": "Cru",
    "Cygni": "Cyg", "Herculis": "Her", "Leonis": "Leo", "Orionis": "Ori",
    "Piscium": "Psc", "Sagittarii": "Sgr", "Scorpii": "Sco", "Tauri": "Tau",
    "Ursae Majoris": "UMa", "Ursae Minoris": "UMi", "Virginis": "Vir",
}


def norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def load_asterisms(path: Path):
    """Read only the stable name/status/members fields from the catalog.

    The catalog is intentionally human-readable and contains prose notes with
    punctuation that need not obey strict YAML scalar quoting. Geometry needs
    only these three machine fields, so parse them directly and fail closed.
    """
    entries = []
    current = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
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


def load_bayer(path: Path):
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    proper = {norm_name(r["proper"]): r for r in rows if r.get("proper")}
    keyed = {(r["bayer_code"], r["con"]): r for r in rows}
    return proper, keyed


def bayer_lookup(name: str, proper, keyed):
    p = proper.get(norm_name(name))
    if p:
        return p
    for constellation, abbr in sorted(CONSTELLATION_TO_ABBR.items(), key=lambda x: -len(x[0])):
        suffix = " " + constellation
        if name.endswith(suffix):
            greek = name[:-len(suffix)]
            code = GREEK_TO_CODE.get(greek)
            if code:
                return keyed.get((code, abbr))
    return None


def sesame_lookup(name: str, timeout: float = 30.0):
    url = SESAME.format(urllib.parse.quote(name, safe=""))
    req = urllib.request.Request(url, headers={"User-Agent": "Star-Almanack/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = response.read()
    root = ET.fromstring(payload)
    for resolver in root.iter("Resolver"):
        ra = resolver.findtext("jradeg")
        dec = resolver.findtext("jdedeg")
        if ra is not None and dec is not None:
            oname = resolver.findtext("oname") or name
            return float(ra) / 15.0, float(dec), oname.strip(), url
    raise RuntimeError(f"Sesame could not resolve {name!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asterisms", type=Path, default=DEFAULT_ASTERISMS)
    ap.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    ap.add_argument("--bayer", type=Path, default=DEFAULT_BAYER)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--delay", type=float, default=0.15, help="seconds between Sesame requests")
    args = ap.parse_args()

    catalog = load_asterisms(args.asterisms)
    overrides_doc = yaml.safe_load(args.overrides.read_text(encoding="utf-8"))
    overrides = {r["designation"]: r["resolved_to"] for r in overrides_doc.get("resolutions", [])}
    proper, keyed = load_bayer(args.bayer)

    out = []
    cache = {}
    for asterism in catalog:
        for member in asterism["members"]:
            query_name = overrides.get(member, member)
            row = None if member in overrides else bayer_lookup(member, proper, keyed)
            if row is not None:
                ra_h = float(row["ra_h"])
                dec_deg = float(row["dec_deg"])
                resolved = row.get("proper") or row.get("bayer") or member
                source = "Star Almanack expanded-bayer-stars.csv"
                source_id = f"HIP {row['hip']}" if row.get("hip") else (f"HD {row['hd']}" if row.get("hd") else "")
            else:
                if query_name not in cache:
                    cache[query_name] = sesame_lookup(query_name)
                    time.sleep(args.delay)
                ra_h, dec_deg, resolved, source_url = cache[query_name]
                source = "CDS Sesame/SIMBAD"
                source_id = source_url
            out.append({
                "asterism": asterism["name"],
                "member": member,
                "resolved_object": resolved,
                "ra_h": f"{ra_h:.10f}",
                "dec_deg": f"{dec_deg:.10f}",
                "coordinate_source": source,
                "source_id": source_id,
                "override": query_name if query_name != member else "",
            })

    fields = ["asterism", "member", "resolved_object", "ra_h", "dec_deg", "coordinate_source", "source_id", "override"]
    with args.output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out)
    print(f"Wrote {len(out)} member rows for {len(catalog)} asterisms to {args.output}")


if __name__ == "__main__":
    main()
