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
    figures = {}
    current = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("* "):
            current = line[2:].strip()
            figures[current] = []
        elif current and line.startswith("["):
            ids = json.loads(line)
            figures[current].extend(int(re.sub(r"\D", "", str(v))) for v in ids)
    if len(figures) != 88:
        raise RuntimeError(f"expected 88 constellation entries; parsed {len(figures)}")
    actual_no_figure = {name for name, ids in figures.items() if not ids}
    if actual_no_figure != NO_FIGURE:
        raise RuntimeError(f"unexpected no-figure set: {sorted(actual_no_figure)}")
    return figures


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
        # Cheap declination window before the spherical distance.
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


def build_constellations(figures, hyg_by_hip, member_path: Path, summary_path: Path):
    members = []
    summaries = []
    for name, ids in figures.items():
        unique_ids = list(dict.fromkeys(ids))
        if not unique_ids:
            summaries.append({
                "constellation": name,
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
                raise RuntimeError(f"IAU figure {name}: HIP {hip} missing from HYG")
            mags.append(row["mag"])
            members.append({
                "constellation": name,
                "hip": hip,
                "proper": row["proper"],
                "bayer": row["bayer"],
                "con": row["con"],
                "v_mag": f"{row['mag']:.3f}",
                "magnitude_source": "HYG v4.1",
            })
        median_v, observer_class = observer_class_for_members(mags)
        summaries.append({
            "constellation": name,
            "figure_status": "stick figure",
            "member_count": len(unique_ids),
            "median_v_mag": f"{median_v:.3f}",
            "observer_class": observer_class,
        })
    if sum(r["figure_status"] == "stick figure" for r in summaries) != 86:
        raise RuntimeError("constellation figure count is not 86")
    write_csv(member_path, members, ["constellation", "hip", "proper", "bayer", "con", "v_mag", "magnitude_source"])
    write_csv(summary_path, summaries, ["constellation", "figure_status", "member_count", "median_v_mag", "observer_class"])


def build_asterisms(coord_path: Path, hyg_by_hip, hyg_rows, max_arcsec, member_path: Path, summary_path: Path):
    out = []
    grouped = defaultdict(list)
    with coord_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            hip_match = re.fullmatch(r"HIP\s+(\d+)", r.get("source_id", "").strip())
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
    figures = parse_iau_figures(args.iau_figures)
    build_constellations(figures, hyg_by_hip, args.constellation_members, args.constellation_summary)
    build_asterisms(args.asterism_coordinates, hyg_by_hip, hyg_rows, args.max_crossmatch_arcsec, args.asterism_members, args.asterism_summary)
    print("PASS: built 86 constellation stick-figure classifications, 2 explicit no-figure states, and 25 asterism classifications")


if __name__ == "__main__":
    main()
