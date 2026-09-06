#!/usr/bin/env python3
"""Audit every catalog-backed stellar entry in the 2026 Almanack.

Checks all bright-star and Bayer visibility rows against almanack-expanded.md.
The authoritative source magnitudes retain their original precision; this audit
checks only observer-facing presentation:
- proper name where available;
- Bayer designation in Greek notation;
- whole-number V magnitude whenever an authoritative source magnitude exists;
- declination band followed by observing season;
- exactly one calendar representation on the assigned best-visibility date.

Permanent regression stars: Enif, Shaula, and alpha Comae Berenices (Diadem).
"""
from __future__ import annotations

import csv
import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).parent
ALMANACK = ROOT / "almanack-expanded.md"
BAYER = ROOT / "expanded-bayer-visibility-2026.csv"
BRIGHT = ROOT / "bright-star-visibility-2026.csv"

PERMANENT_REGRESSION_STARS = (
    ("Enif", "ε Peg"),
    ("Shaula", "λ Sco"),
    ("Diadem", "α Com"),
)

GREEK = {
    "Alp": "α", "Bet": "β", "Gam": "γ", "Del": "δ", "Eps": "ε",
    "Zet": "ζ", "Eta": "η", "The": "θ", "Iot": "ι", "Kap": "κ",
    "Lam": "λ", "Mu": "μ", "Nu": "ν", "Xi": "ξ", "Omi": "ο",
    "Pi": "π", "Rho": "ρ", "Sig": "σ", "Tau": "τ", "Ups": "υ",
    "Phi": "φ", "Chi": "χ", "Psi": "ψ", "Ome": "ω",
}


def designation_key(code: str, con: str) -> str:
    m = re.fullmatch(r"([A-Z][a-z]{2})(?:-?(\d+))?", (code or "").strip())
    if not m:
        return f"{code} {con}".strip().casefold()
    suffix = m.group(2)
    if suffix:
        return f"{m.group(1)} {suffix} {con}".strip().casefold()
    return f"{m.group(1)} {con}".strip().casefold()


def bayer_display(code: str, con: str) -> str:
    m = re.fullmatch(r"([A-Z][a-z]{2})(?:-?(\d+))?", (code or "").strip())
    if not m:
        return f"{code} {con}".strip()
    symbol = GREEK.get(m.group(1), m.group(1))
    suffix = m.group(2) or ""
    return f"{symbol}{suffix} {con}".strip()


def whole_mag(value: str) -> str:
    return str(int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def declination_band(dec_deg: str) -> str:
    dec = float(dec_deg)
    if dec > 23.44:
        return "Northern"
    if dec < -23.44:
        return "Southern"
    return "Tropical"


def season_for(d: date) -> str:
    md = (d.month, d.day)
    if (3, 20) <= md < (6, 21):
        return "Spring"
    if (6, 21) <= md < (9, 22):
        return "Summer"
    if (9, 22) <= md < (12, 21):
        return "Autumn"
    return "Winter"


def calendar_events() -> dict[str, list[str]]:
    text = ALMANACK.read_text(encoding="utf-8")
    calendar_text = text.split("\n## Expanded α and β Star Catalog\n", 1)[0]
    row_re = re.compile(
        r"(?m)^\| (?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), ([A-Z][a-z]{2}) (\d{2}), (2025|2026|2027) \| [^|]+ \| ([^|]*) \|$"
    )
    out: dict[str, list[str]] = {}
    for m in row_re.finditer(calendar_text):
        d = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y").date().isoformat()
        out[d] = [part.strip() for part in m.group(4).split("<br>") if part.strip()]
    return out


def source_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    index: dict[tuple[str, str], int] = {}

    def add_or_prefer_named(r: dict[str, str], code: str) -> None:
        r = dict(r)
        r["_code"] = code
        key = (r["best_date"], designation_key(code, r.get("con", "")))
        if key not in index:
            index[key] = len(rows)
            rows.append(r)
            return
        old = rows[index[key]]
        if not (old.get("proper") or "").strip() and (r.get("proper") or "").strip():
            rows[index[key]] = r

    with BRIGHT.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            add_or_prefer_named(row, row.get("bayer", ""))

    with BAYER.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            add_or_prefer_named(row, row.get("bayer_code", ""))

    return rows


def canonical_name_match(part: str, name: str) -> bool:
    p = part.strip().casefold()
    n = name.strip().casefold()
    return p == n or p.startswith(n + " (") or p.startswith(n + " —")


def isolate_entry(parts: list[str], proper: str, designation: str) -> list[str]:
    if proper:
        matches = [part for part in parts if canonical_name_match(part, proper)]
        if matches:
            return matches
    return [part for part in parts if canonical_name_match(part, designation)]


def audit_permanent_regressions(events: dict[str, list[str]], defects: list[str]) -> None:
    all_entries = [entry for parts in events.values() for entry in parts]
    for proper, designation in PERMANENT_REGRESSION_STARS:
        matches = [
            entry for entry in all_entries
            if canonical_name_match(entry, proper) or canonical_name_match(entry, designation)
        ]
        if len(matches) != 1:
            defects.append(
                f"permanent regression {proper} ({designation}): expected exactly one calendar entry, found {len(matches)}"
            )
            continue
        entry = matches[0]
        if proper not in entry or designation not in entry:
            defects.append(
                f"permanent regression {proper} ({designation}): name/designation pair damaged; entry={entry}"
            )
        if not re.search(r"\bV\s+[+-]?\d+\b", entry):
            defects.append(
                f"permanent regression {proper} ({designation}): whole-number magnitude missing; entry={entry}"
            )


def main() -> None:
    events = calendar_events()
    rows = source_rows()
    defects: list[str] = []
    audited = 0

    for r in rows:
        best_date = r.get("best_date", "")
        code = r.get("_code", "")
        con = (r.get("con") or "").strip()
        proper = (r.get("proper") or "").strip()
        designation = bayer_display(code, con)
        parts = events.get(best_date, [])
        matches = isolate_entry(parts, proper, designation)
        label = proper or designation

        if len(matches) != 1:
            defects.append(
                f"{best_date} {label}: expected exactly one entry, found {len(matches)}; day={' | '.join(parts)}"
            )
            continue

        entry = matches[0]
        audited += 1

        if proper:
            expected_name = f"{proper} ({designation})"
            if expected_name not in entry:
                defects.append(f"{best_date} {label}: missing/incorrect Bayer designation; entry={entry}")
        elif designation not in entry:
            defects.append(f"{best_date} {label}: missing Bayer designation; entry={entry}")

        source_mag = (
            (r.get("representative_vmax") or "").strip()
            or (r.get("mag") or "").strip()
            or (r.get("catalog_v") or "").strip()
        )
        if not source_mag:
            defects.append(f"{best_date} {label}: no authoritative source magnitude")
        else:
            expected_v = f"V {whole_mag(source_mag)}"
            if expected_v not in entry:
                defects.append(f"{best_date} {label}: expected {expected_v}; entry={entry}")
            if re.search(r"\bV\s+[+-]?\d+\.\d+", entry):
                defects.append(f"{best_date} {label}: decimal magnitude survived Almanack presentation; entry={entry}")

        dec = (r.get("dec_deg") or "").strip()
        if dec:
            expected_tail = f"{declination_band(dec)} {season_for(date.fromisoformat(best_date))}"
            if expected_tail not in entry:
                defects.append(f"{best_date} {label}: expected {expected_tail}; entry={entry}")

    audit_permanent_regressions(events, defects)

    print(f"Audited {audited} isolated stellar entries from {len(rows)} catalog-backed placements.")
    print("Permanent regression stars: Enif, Shaula, Diadem (α Com).")
    if defects:
        print(f"FAIL: {len(defects)} stellar presentation defects")
        for defect in defects:
            print(f"- {defect}")
        raise SystemExit(1)

    print("PASS: all catalog-backed stellar entries and permanent regression stars have whole-number magnitudes and required presentation.")


if __name__ == "__main__":
    main()
