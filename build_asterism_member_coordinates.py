#!/usr/bin/env python3
"""Build the resolved stellar cross-match for the 25 core asterisms.

Policy:
  1. Use Star Almanack's expanded Bayer catalog wherever it contains the member.
  2. Apply explicit ambiguity overrides from asterism-coordinate-resolution.yaml.
  3. Resolve remaining stellar designations against the pinned HYG v4.1 source.
  4. When a name is not represented uniquely in HYG, use CDS Sesame/SIMBAD only
     to establish the object's sky position, then cross-match that position back
     to a concrete magnitude-bearing HYG object.

The output is the single resolved member dataset consumed downstream. It carries
coordinates and visual magnitude together with explicit provenance. Downstream
geometry, median-magnitude, and display code must derive values from this file
rather than independently re-resolving stellar facts.
"""
from __future__ import annotations

import argparse
import csv
import math
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
HYG_PIN = "astronexus/HYG-Database@3bf37f4b2d5460e1278286320d1d62fab9b493c1:hyg/CURRENT/hygdata_v41.csv"
MAX_POSITIONAL_MATCH_ARCSEC = 60.0

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
    "Vulpeculae": "Vul",
}


def norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


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


def load_bayer(path: Path):
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    proper = {norm_name(r["proper"]): r for r in rows if r.get("proper")}
    keyed = {(r["bayer_code"], r["con"]): r for r in rows}
    return proper, keyed


def designation_parts(name: str):
    for constellation, abbr in sorted(CONSTELLATION_TO_ABBR.items(), key=lambda x: -len(x[0])):
        suffix = " " + constellation
        if name.endswith(suffix):
            return name[:-len(suffix)].strip(), abbr
    return None, None


def bayer_lookup(name: str, proper, keyed):
    p = proper.get(norm_name(name))
    if p:
        return p
    designation, abbr = designation_parts(name)
    if not designation:
        return None
    match = re.fullmatch(r"([A-Za-z]+)(\d*)", designation)
    if not match:
        return None
    greek, component = match.groups()
    code = GREEK_TO_CODE.get(greek)
    if not code:
        return None
    return keyed.get((f"{code}{component}", abbr))


def load_hyg(path: Path):
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8-sig")))
    required = {"id", "hip", "hd", "hr", "proper", "ra", "dec", "mag", "bayer", "flam", "con"}
    missing = required.difference(rows[0].keys() if rows else set())
    if missing:
        raise RuntimeError(f"HYG input missing columns: {sorted(missing)}")

    indexes = {
        "proper": {}, "bayer": {}, "flam": {}, "hip": {}, "hd": {}, "hr": {}, "hyg": {},
    }
    for row in rows:
        proper = (row.get("proper") or "").strip()
        con = (row.get("con") or "").strip()
        bayer = (row.get("bayer") or "").strip()
        flam = (row.get("flam") or "").strip()
        if proper:
            indexes["proper"].setdefault(norm_name(proper), []).append(row)
        if bayer and con:
            indexes["bayer"].setdefault((bayer, con), []).append(row)
        if flam and con:
            indexes["flam"].setdefault((flam, con), []).append(row)
        for field in ("hip", "hd", "hr", "id"):
            value = (row.get(field) or "").strip()
            if value:
                key = "hyg" if field == "id" else field
                indexes[key][value] = row
    return rows, indexes


def hyg_identity(row):
    for field, label in (("hip", "HIP"), ("hd", "HD"), ("hr", "HR"), ("id", "HYG")):
        value = (row.get(field) or "").strip()
        if value:
            return f"{label} {value}"
    return ""


def hyg_row_complete(row) -> bool:
    if row is None:
        return False
    try:
        float(row.get("ra") or "")
        float(row.get("dec") or "")
        float(row.get("mag") or "")
    except (TypeError, ValueError):
        return False
    return bool(hyg_identity(row))


def unique_complete(candidates):
    complete = [row for row in candidates if hyg_row_complete(row)]
    return complete[0] if len(complete) == 1 else None


def hyg_lookup(name: str, indexes):
    direct = unique_complete(indexes["proper"].get(norm_name(name), []))
    if direct:
        return direct

    match = re.fullmatch(r"(?i)(HIP|HD|HR|HYG)\s*(\d+)", name.strip())
    if match:
        catalog, number = match.groups()
        row = indexes[catalog.lower()].get(number)
        return row if hyg_row_complete(row) else None

    designation, abbr = designation_parts(name)
    if not designation:
        short = re.fullmatch(r"([A-Za-z]+)(\d*)\s+([A-Z][A-Za-z]{2})", name.strip())
        if short:
            greek, component, abbr = short.groups()
            code = GREEK_TO_CODE.get(greek)
            if code:
                return unique_complete(indexes["bayer"].get((f"{code}{component}", abbr), []))
        return None

    flamsteed = re.fullmatch(r"(\d+)", designation)
    if flamsteed:
        return unique_complete(indexes["flam"].get((flamsteed.group(1), abbr), []))

    bayer = re.fullmatch(r"([A-Za-z]+)(\d*)", designation)
    if bayer:
        greek, component = bayer.groups()
        code = GREEK_TO_CODE.get(greek)
        if code:
            return unique_complete(indexes["bayer"].get((f"{code}{component}", abbr), []))
    return None


def angular_separation_arcsec(ra1_h, dec1_deg, ra2_h, dec2_deg):
    ra1 = math.radians(ra1_h * 15.0)
    ra2 = math.radians(ra2_h * 15.0)
    dec1 = math.radians(dec1_deg)
    dec2 = math.radians(dec2_deg)
    cos_sep = (
        math.sin(dec1) * math.sin(dec2)
        + math.cos(dec1) * math.cos(dec2) * math.cos(ra1 - ra2)
    )
    cos_sep = max(-1.0, min(1.0, cos_sep))
    return math.degrees(math.acos(cos_sep)) * 3600.0


def hyg_positional_match(ra_h, dec_deg, rows, max_arcsec=MAX_POSITIONAL_MATCH_ARCSEC):
    """Return the unique nearest complete HYG object within a strict radius."""
    matches = []
    for row in rows:
        if not hyg_row_complete(row):
            continue
        sep = angular_separation_arcsec(ra_h, dec_deg, float(row["ra"]), float(row["dec"]))
        if sep <= max_arcsec:
            matches.append((sep, hyg_identity(row), row))
    if not matches:
        return None, None
    matches.sort(key=lambda item: (item[0], item[1]))
    # Reject an effectively tied nearest-neighbour result rather than guessing.
    if len(matches) > 1 and abs(matches[1][0] - matches[0][0]) < 0.01:
        return None, None
    return matches[0][2], matches[0][0]


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
    ap.add_argument("--hyg", type=Path, required=True, help="Pinned HYG v4.1 CSV used as the authoritative stellar source")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--delay", type=float, default=0.15, help="seconds between Sesame requests")
    args = ap.parse_args()

    catalog = load_asterisms(args.asterisms)
    overrides_doc = yaml.safe_load(args.overrides.read_text(encoding="utf-8"))
    overrides = {r["designation"]: r["resolved_to"] for r in overrides_doc.get("resolutions", [])}
    proper, keyed = load_bayer(args.bayer)
    hyg_rows, hyg = load_hyg(args.hyg)

    out = []
    cache = {}
    unresolved_magnitudes = []
    for asterism in catalog:
        for member in asterism["members"]:
            query_name = overrides.get(member, member)
            row = None if member in overrides else bayer_lookup(member, proper, keyed)
            if row is not None and row.get("mag", "").strip():
                ra_h = float(row["ra_h"])
                dec_deg = float(row["dec_deg"])
                resolved = row.get("proper") or row.get("bayer") or member
                source = "Star Almanack expanded-bayer-stars.csv"
                source_id = f"HIP {row['hip']}" if row.get("hip") else (f"HD {row['hd']}" if row.get("hd") else "")
                magnitude = row.get("mag", "").strip()
                magnitude_source = source if source_id else ""
                magnitude_source_id = source_id if magnitude else ""
            else:
                hrow = hyg_lookup(query_name, hyg)
                match_note = ""
                if hrow is None:
                    if query_name not in cache:
                        cache[query_name] = sesame_lookup(query_name)
                        time.sleep(args.delay)
                    sesame_ra_h, sesame_dec_deg, sesame_name, source_url = cache[query_name]
                    hrow, separation = hyg_positional_match(sesame_ra_h, sesame_dec_deg, hyg_rows)
                    if hrow is not None:
                        match_note = f"; positional cross-match {separation:.3f} arcsec from CDS Sesame/SIMBAD {sesame_name}"
                    else:
                        ra_h = sesame_ra_h
                        dec_deg = sesame_dec_deg
                        resolved = sesame_name
                        source = "CDS Sesame/SIMBAD"
                        source_id = source_url
                        magnitude = ""
                        magnitude_source = ""
                        magnitude_source_id = ""

                if hrow is not None:
                    ra_h = float(hrow["ra"])
                    dec_deg = float(hrow["dec"])
                    resolved = (hrow.get("proper") or "").strip() or query_name
                    source = "Pinned HYG v4.1" + match_note
                    source_id = hyg_identity(hrow)
                    magnitude = (hrow.get("mag") or "").strip()
                    magnitude_source = f"Pinned HYG v4.1 ({HYG_PIN})"
                    magnitude_source_id = source_id

            if not magnitude or not magnitude_source or not magnitude_source_id:
                unresolved_magnitudes.append(f"{asterism['name']}: {member} -> {query_name}")

            out.append({
                "asterism": asterism["name"],
                "member": member,
                "resolved_object": resolved,
                "ra_h": f"{ra_h:.10f}",
                "dec_deg": f"{dec_deg:.10f}",
                "mag": magnitude,
                "coordinate_source": source,
                "coordinate_source_id": source_id,
                "magnitude_source": magnitude_source,
                "magnitude_source_id": magnitude_source_id,
                "override": query_name if query_name != member else "",
            })

    fields = [
        "asterism", "member", "resolved_object", "ra_h", "dec_deg", "mag",
        "coordinate_source", "coordinate_source_id", "magnitude_source",
        "magnitude_source_id", "override",
    ]
    with args.output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out)

    if unresolved_magnitudes:
        joined = "\n  - ".join(unresolved_magnitudes)
        raise SystemExit(
            "Magnitude provenance incomplete; refusing to produce median-ready member data:\n  - " + joined
        )

    print(f"Wrote {len(out)} resolved member rows for {len(catalog)} asterisms to {args.output}")
    print("PASS: every asterism member has numeric stellar magnitude provenance")


if __name__ == "__main__":
    main()
