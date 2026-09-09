#!/usr/bin/env python3
"""Build source-grounded member magnitudes and observer classes for stellar patterns.

Inputs are deliberately external/pinned stellar and stick-figure sources plus the
repository's resolved asterism coordinates. Rendering code must consume the
outputs; it must not invent memberships or observer classes.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT.parent / "tools"
sys.path.insert(0, str(TOOLS))
from observer_classification import observer_class_for_members  # noqa: E402

NO_FIGURE = {"Mensa", "Microscopium"}
SERPENS_COMPONENTS = {
    # The adopted source stores the two disconnected parts of the single IAU
    # constellation Serpens as A/B sections. Preserve them as distinct patterns.
    # SerpensA contains HIP 92946 (theta1 Serpentis / Alya) in Serpens Cauda;
    # SerpensB contains HIP 79195 in Serpens Caput.
    "SerpensA": ("Serpens", "Serpens Cauda"),
    "SerpensB": ("Serpens", "Serpens Caput"),
}


def load_hyg(path: Path):
    by_hip = {}
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("hip") or not r.get("mag"):
                continue
            try:
                hip = int(r["hip"])
                mag = float(r["mag"])
                ra_h = float(r["ra"])
                dec_deg = float(r["dec"])
            except ValueError:
                continue
            row = {
                "hip": hip,
                "mag": mag,
                "ra_h": ra_h,
                "dec_deg": dec_deg,
                "proper": r.get("proper", ""),
                "bayer": r.get("bayer", ""),
                "con": r.get("con", ""),
            }
            if hip in by_hip:
                raise RuntimeError(f"duplicate HYG HIP {hip}")
            by_hip[hip] = row
            rows.append(row)
    if not by_hip:
        raise RuntimeError(f"no HYG HIP/magnitude rows parsed from {path}")
    return by_hip, rows


def parse_iau_figures(path: Path):
    patterns = {}
    current = None
    source_sections = 0
    parents = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("* "):
            source_sections += 1
            source_name = line[2:].strip()
            parent, pattern = SERPENS_COMPONENTS.get(source_name, (source_name, source_name))
            current = pattern
            parents.add(parent)
            if current in patterns:
                raise RuntimeError(f"duplicate pattern label {current}")
            patterns[current] = {
                "constellation": parent,
                "pattern": pattern,
                "source_section": source_name,
                "ids": [],
            }
        elif current and line.startswith("["):
            ids = json.loads(line)
            patterns[current]["ids"].extend(int(re.sub(r"\D", "", str(v))) for v in ids)
    if source_sections != 89:
        raise RuntimeError(f"expected 89 source sections; parsed {source_sections}")
    if len(patterns) != 89:
        raise RuntimeError(f"expected 89 distinct pattern records; parsed {len(patterns)}")
    if len(parents) != 88:
        raise RuntimeError(f"expected 88 parent IAU constellations; parsed {len(parents)}")
    actual_no_figure = {name for name, rec in patterns.items() if not rec["ids"]}
    if actual_no_figure != NO_FIGURE:
        raise RuntimeError(f"unexpected no-figure set: {sorted(actual_no_figure)}")
    if {patterns[n]["constellation"] for n in ("Serpens Caput", "Serpens Cauda")} != {"Serpens"}:
        raise RuntimeError("Serpens components do not share parent constellation Serpens")
    return patterns


def separation_arcsec(ra1_h, dec1_deg, ra2_h, dec2_deg):
    ra1 = math.radians(ra1_h * 15.0)
    ra2 = math.radians(ra2_h * 15.0)
    d1 = math.radians(dec1_deg)
    d2 = math.radians(dec2_deg)
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(ra1 - ra2)
    c = max(-1.0, min(1.0, c))
    return math.degrees(math.acos(c)) * 3600.0


def nearest_hyg(ra_h, dec_deg, hyg_rows, max_arcsec):
    ranked = []
    for row in hyg_rows:
        if abs(row["dec_deg"] - dec_deg) * 3600.0 > max_arcsec:
            continue
        sep = separation_arcsec(ra_h, dec_deg, row["ra_h"], row["dec_deg"])
        if sep <= max_arcsec:
            ranked.append((sep, row))
    ranked.sort(key=lambda item: item[0])
    if not ranked:
        raise RuntimeError(f"no HYG match within {max_arcsec} arcsec at RA={ra_h} Dec={dec_deg}")
    if len(ranked) > 1 and abs(ranked[1][0] - ranked[0][0]) < 0.25:
        raise RuntimeError(
            f"ambiguous HYG positional match at RA={ra_h} Dec={dec_deg}: "
            f"HIP {ranked[0][1]['hip']} {ranked[0][0]:.3f} arcsec vs "
            f"HIP {ranked[1][1]['hip']} {ranked[1][0]:.3f} arcsec"
        )
    return ranked[0]


def write_csv(path: Path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def build_constellations(patterns, hyg_by_hip, member_path: Path, summary_path: Path):
    members = []
    summaries = []
    for pattern, rec in patterns.items():
        parent = rec["constellation"]
        source_section = rec["source_section"]
        unique_ids = list(dict.fromkeys(rec["ids"]))
        if not unique_ids:
            summaries.append({
                "constellation": parent,
                "pattern": pattern,
                "source_section": source_section,
                "figure_status": "no stick figure",
                "member_count": 0,
                "median_v_mag": "",
                "observer_class": "",
            })
            continue
        mags = []
        for hip in unique_ids:
            row = hyg_by_hip.get(hip)
            if row is None:
                raise RuntimeError(f"IAU figure {pattern}: HIP {hip} missing from HYG")
            mags.append(row["mag"])
            members.append({
                "constellation": parent,
                "pattern": pattern,
                "source_section": source_section,
                "hip": hip,
                "proper": row["proper"],
                "bayer": row["bayer"],
                "con": row["con"],
                "v_mag": f"{row['mag']:.3f}",
                "magnitude_source": "HYG v4.1",
            })
        median_v, observer_class = observer_class_for_members(mags)
        summaries.append({
            "constellation": parent,
            "pattern": pattern,
            "source_section": source_section,
            "figure_status": "stick figure",
            "member_count": len(unique_ids),
            "median_v_mag": f"{median_v:.3f}",
            "observer_class": observer_class,
        })
    figure_components = [r for r in summaries if r["figure_status"] == "stick figure"]
    figure_parents = {r["constellation"] for r in figure_components}
    if len(figure_components) != 87:
        raise RuntimeError(f"constellation stick-figure component count is not 87: {len(figure_components)}")
    if len(figure_parents) != 86:
        raise RuntimeError(f"constellations with stick figures count is not 86: {len(figure_parents)}")
    write_csv(
        member_path,
        members,
        ["constellation", "pattern", "source_section", "hip", "proper", "bayer", "con", "v_mag", "magnitude_source"],
    )
    write_csv(
        summary_path,
        summaries,
        ["constellation", "pattern", "source_section", "figure_status", "member_count", "median_v_mag", "observer_class"],
    )


def build_asterisms(coord_path: Path, hyg_by_hip, hyg_rows, max_arcsec, member_path: Path, summary_path: Path):
    out = []
    grouped = defaultdict(list)
    with coord_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            hip_match = re.search(r"(?:^|;\s*)HIP\s+(\d+)(?:;|$)", r.get("source_id", "").strip())
            if hip_match:
                hip = int(hip_match.group(1))
                h = hyg_by_hip.get(hip)
                if h is None:
                    raise RuntimeError(f"{r['asterism']} / {r['member']}: HIP {hip} missing from HYG")
                sep = separation_arcsec(float(r["ra_h"]), float(r["dec_deg"]), h["ra_h"], h["dec_deg"])
                method = "existing HIP source_id"
            else:
                sep, h = nearest_hyg(float(r["ra_h"]), float(r["dec_deg"]), hyg_rows, max_arcsec)
                hip = h["hip"]
                method = "J2000 positional cross-match"
            grouped[r["asterism"]].append(h["mag"])
            out.append({
                "asterism": r["asterism"],
                "member": r["member"],
                "resolved_object": r["resolved_object"],
                "hip": hip,
                "v_mag": f"{h['mag']:.3f}",
                "match_method": method,
                "separation_arcsec": f"{sep:.3f}",
                "magnitude_source": "HYG v4.1",
            })
    summaries = []
    for name in sorted(grouped):
        median_v, observer_class = observer_class_for_members(grouped[name])
        summaries.append({
            "asterism": name,
            "member_count": len(grouped[name]),
            "median_v_mag": f"{median_v:.3f}",
            "observer_class": observer_class,
        })
    if len(summaries) != 25:
        raise RuntimeError(f"expected 25 asterisms; got {len(summaries)}")
    write_csv(member_path, out, ["asterism", "member", "resolved_object", "hip", "v_mag", "match_method", "separation_arcsec", "magnitude_source"])
    write_csv(summary_path, summaries, ["asterism", "member_count", "median_v_mag", "observer_class"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hyg", type=Path)
    ap.add_argument("iau_figures", type=Path)
    ap.add_argument("--asterism-coordinates", type=Path, default=ROOT / "asterism-member-coordinates.csv")
    ap.add_argument("--max-crossmatch-arcsec", type=float, default=60.0)
    ap.add_argument("--constellation-members", type=Path, default=ROOT / "constellation-stick-figure-members.csv")
    ap.add_argument("--constellation-summary", type=Path, default=ROOT / "constellation-pattern-magnitudes.csv")
    ap.add_argument("--asterism-members", type=Path, default=ROOT / "asterism-member-magnitudes.csv")
    ap.add_argument("--asterism-summary", type=Path, default=ROOT / "asterism-pattern-magnitudes.csv")
    args = ap.parse_args()

    hyg_by_hip, hyg_rows = load_hyg(args.hyg)
    patterns = parse_iau_figures(args.iau_figures)
    build_constellations(patterns, hyg_by_hip, args.constellation_members, args.constellation_summary)
    build_asterisms(args.asterism_coordinates, hyg_by_hip, hyg_rows, args.max_crossmatch_arcsec, args.asterism_members, args.asterism_summary)
    print("PASS: built 87 stick-figure component classifications across 86 constellations, 2 explicit no-figure states, and 25 asterism classifications")


if __name__ == "__main__":
    main()
