#!/usr/bin/env python3
"""Build the Star Almanack second-magnitude bright-star catalog.

Selection rule:
    representative maximum Johnson V <= +2.50

Baseline rows come from a pinned HYG v4.1 catalog supplied on the command line.
The builder then applies the audited naked-eye system reconciliation in
bright-system-reconciliation.csv so the output contains observer-relevant
stellar systems rather than raw catalog/component rows.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from pathlib import Path

BAYER_RE = re.compile(r"^(Alp|Bet)-?(\d*)$")


def parse_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_bayer_code(value: str) -> str:
    value = (value or "").strip()
    match = BAYER_RE.match(value)
    if not match:
        return ""
    return match.group(1) + match.group(2)


def load_alpha_beta_keys(path: Path) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            code = (row.get("bayer_code") or "").strip()
            con = (row.get("con") or "").strip()
            if code and con:
                keys.add((code, con))
    return keys


def load_reconciliation(path: Path):
    excluded: set[str] = set()
    merge_rules: list[dict[str, str]] = []
    if not path.exists():
        raise SystemExit(f"Missing required system reconciliation file: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            action = (row.get("action") or "").strip()
            ids = [x.strip() for x in (row.get("hyg_ids") or "").split(";") if x.strip()]
            if action in {"exclude", "suppress-component"}:
                excluded.update(ids)
            elif action == "merge":
                if len(ids) < 2:
                    raise SystemExit(f"Merge rule requires at least two HYG ids: {row}")
                row["_ids"] = ids
                merge_rules.append(row)
            else:
                raise SystemExit(f"Unknown reconciliation action {action!r}: {row}")
    return excluded, merge_rules


def joined(rows: list[dict[str, str]], field: str) -> str:
    vals = []
    for row in rows:
        value = (row.get(field) or "").strip()
        if value and value not in vals:
            vals.append(value)
    return ";".join(vals)


def system_row(
    proper: str,
    bayer: str,
    con: str,
    ra_h: str,
    dec_deg: str,
    catalog_v: str,
    representative_vmax: str,
    basis: str,
    alpha_beta: set[tuple[str, str]],
    hyg_id: str,
    hip: str = "",
    hd: str = "",
    hr: str = "",
) -> dict[str, str]:
    bayer_code = normalize_bayer_code(bayer)
    is_alpha_beta = bool(bayer_code and con and (bayer_code, con) in alpha_beta)
    return {
        "proper": proper,
        "bayer": bayer,
        "con": con,
        "ra_h": ra_h,
        "dec_deg": dec_deg,
        "catalog_v": catalog_v,
        "representative_vmax": representative_vmax,
        "brightness_basis": basis,
        "in_alpha_beta_layer": "yes" if is_alpha_beta else "no",
        "hyg_id": hyg_id,
        "hip": hip,
        "hd": hd,
        "hr": hr,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("hyg", type=Path)
    parser.add_argument("output", type=Path, nargs="?", default=Path("bright-stars-2mag.csv"))
    parser.add_argument("--bayer", type=Path, default=Path("expanded-bayer-stars.csv"))
    parser.add_argument("--reconciliation", type=Path, default=Path("bright-system-reconciliation.csv"))
    parser.add_argument("--limit", type=float, default=2.50)
    args = parser.parse_args()

    alpha_beta = load_alpha_beta_keys(args.bayer)
    excluded_ids, merge_rules = load_reconciliation(args.reconciliation)

    with args.hyg.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    by_id = {(row.get("id") or "").strip(): row for row in rows}
    merge_member_ids = {hid for rule in merge_rules for hid in rule["_ids"]}

    selected: list[dict[str, str]] = []
    raw_candidates = 0
    for row in rows:
        mag = parse_float(row.get("mag", ""))
        if mag is None or mag > args.limit:
            continue
        raw_candidates += 1
        hyg_id = (row.get("id") or "").strip()
        if hyg_id in excluded_ids or hyg_id in merge_member_ids:
            continue
        selected.append(system_row(
            proper=(row.get("proper") or "").strip(),
            bayer=(row.get("bayer") or "").strip(),
            con=(row.get("con") or "").strip(),
            ra_h=row.get("ra", ""),
            dec_deg=row.get("dec", ""),
            catalog_v=row.get("mag", ""),
            representative_vmax=row.get("mag", ""),
            basis="HYG v4.1 catalog V (stable baseline)",
            alpha_beta=alpha_beta,
            hyg_id=hyg_id,
            hip=row.get("hip", ""),
            hd=row.get("hd", ""),
            hr=row.get("hr", ""),
        ))

    for rule in merge_rules:
        members = []
        for hid in rule["_ids"]:
            member = by_id.get(hid)
            if member is None:
                raise SystemExit(f"Reconciliation HYG id {hid} not found")
            mag = parse_float(member.get("mag", ""))
            if mag is None:
                raise SystemExit(f"Reconciliation HYG id {hid} has no usable V magnitude")
            members.append(member)
        flux = sum(10 ** (-0.4 * float(m["mag"])) for m in members)
        combined_mag = -2.5 * math.log10(flux)
        if combined_mag > args.limit:
            continue
        first = members[0]
        bayer = (rule.get("bayer") or "").strip()
        con = (rule.get("con") or "").strip()
        selected.append(system_row(
            proper=(rule.get("system_name") or "").strip(),
            bayer=bayer,
            con=con,
            ra_h=first.get("ra", ""),
            dec_deg=first.get("dec", ""),
            catalog_v=";".join((m.get("mag") or "").strip() for m in members),
            representative_vmax=f"{combined_mag:.2f}",
            basis="flux-combined HYG v4.1 V for unresolved naked-eye system",
            alpha_beta=alpha_beta,
            hyg_id=joined(members, "id"),
            hip=joined(members, "hip"),
            hd=joined(members, "hd"),
            hr=joined(members, "hr"),
        ))

    selected.sort(key=lambda r: (float(r["representative_vmax"]), r["proper"] or r["bayer"], r["con"]))

    fieldnames = [
        "proper", "bayer", "con", "ra_h", "dec_deg", "catalog_v",
        "representative_vmax", "brightness_basis", "in_alpha_beta_layer",
        "hyg_id", "hip", "hd", "hr",
    ]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(selected)

    ab = sum(r["in_alpha_beta_layer"] == "yes" for r in selected)
    non_ab = len(selected) - ab
    print(f"Raw HYG rows at V <= {args.limit:.2f}: {raw_candidates}")
    print(f"Reconciled naked-eye stellar systems: {len(selected)}")
    print(f"Already alpha/beta: {ab}")
    print(f"New non-alpha/beta systems: {non_ab}")
    print("Variable-star boundary decisions are audited separately.")


if __name__ == "__main__":
    main()
