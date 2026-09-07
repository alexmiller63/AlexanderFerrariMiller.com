#!/usr/bin/env python3
"""Populate 2025/2027 constellation geometry without duplicating stellar entries."""
from __future__ import annotations
import csv
import datetime as dt
import importlib.util
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
PUBLIC = ROOT / "almanack"
SOURCE_SITE = SRC / "site"
YEARS = (2025, 2027)
CENTROID_SNAPSHOT = SRC / "constellation-observance-2026.csv"
fspec = importlib.util.spec_from_file_location("fixedsky", ROOT / "tools" / "populate_2025_2027_fixed_sky.py")
fixed = importlib.util.module_from_spec(fspec); assert fspec and fspec.loader; fspec.loader.exec_module(fixed)


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f: return list(csv.DictReader(f))


def preferred_ab(rows, abbr, greek):
    candidates = [r for r in rows if r.get("con") == abbr and r.get("greek") == greek]
    unsuffixed = [r for r in candidates if not r.get("suffix", "").strip()]
    return (unsuffixed or candidates or [None])[0]


def iso_label(d):
    y, w, wd = d.isocalendar(); return f"{y}-W{w:02d}-{wd}"


def build_rows(year):
    bayer = read_csv(SRC / "expanded-bayer-visibility-2026.csv")
    snaps = read_csv(CENTROID_SNAPSHOT)
    if len(snaps) != 88: raise SystemExit(f"Expected 88 centroid snapshot rows, got {len(snaps)}")
    rows = []
    for snap in snaps:
        name, abbr = snap["name"], snap["abbr"]
        ci, cd = fixed.best_visibility(float(snap["centroid_ra_h"]), year)
        alpha, beta = preferred_ab(bayer, abbr, "α"), preferred_ab(bayer, abbr, "β")
        ai = ad = bi = bd = None
        if alpha: ai, ad = fixed.best_visibility(float(alpha["ra_h"]), year)
        if beta: bi, bd = fixed.best_visibility(float(beta["ra_h"]), year)
        rows.append({"name":name,"abbr":abbr,"centroid_ra_h":snap["centroid_ra_h"],"centroid_dec_deg":snap["centroid_dec_deg"],"sampled_area_sq_deg":snap["sampled_area_sq_deg"],"centroid_step_deg":snap["centroid_step_deg"],"alpha_bayer":alpha.get("bayer","") if alpha else "","alpha_ra_h":alpha.get("ra_h","") if alpha else "","alpha_best_instant_utc":ai.strftime("%Y-%m-%d %H:%M") if ai else "","alpha_best_date":ad.isoformat() if ad else "","alpha_iso":iso_label(ad) if ad else "","beta_bayer":beta.get("bayer","") if beta else "","beta_ra_h":beta.get("ra_h","") if beta else "","beta_best_instant_utc":bi.strftime("%Y-%m-%d %H:%M") if bi else "","beta_best_date":bd.isoformat() if bd else "","beta_iso":iso_label(bd) if bd else "","center_best_instant_utc":ci.strftime("%Y-%m-%d %H:%M"),"center_best_date":cd.isoformat(),"center_iso":iso_label(cd)})
    return rows


def write_csv(year, rows):
    out = SRC / "generated" / f"constellation-observance-{year}.csv"; out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def event_map(rows):
    events = defaultdict(list)
    for r in rows: events[dt.date.fromisoformat(r["center_best_date"])].append(f"✦ {r['name']} geometric-center observance")
    return events


def clean_legacy_observances(text):
    cells = re.compile(r'(<td>)(.*?)(</td>)')
    legacy = re.compile(r'^✦ .*? [αβ]-star observance(?:\s*\([^)]*\))?$')
    def repl(m):
        parts = [p for p in m.group(2).split("<br>") if not legacy.match(p.strip())]
        body = "<br>".join(parts) if parts else "—"
        return m.group(1) + body + m.group(3)
    return cells.sub(repl, text)


def inject(root, year, events):
    changed = 0
    for page in sorted((root / str(year)).glob("W*/index.html")):
        text = page.read_text(encoding="utf-8"); original = text; text = clean_legacy_observances(text)
        for d, vals in events.items():
            date_text = d.strftime("%a, %b %d, %Y").replace(" 0", " ")
            pat = re.compile(rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)"); m = pat.search(text)
            if not m: continue
            keep = [] if m.group(2) == "—" else [x for x in m.group(2).split("<br>") if x]
            for v in vals:
                if v not in keep: keep.append(v)
            text = text[:m.start(2)] + "<br>".join(keep) + text[m.end(2):]
        if text != original: page.write_text(text, encoding="utf-8"); changed += 1
    return changed


def main():
    for year in YEARS:
        rows = build_rows(year); write_csv(year, rows); events = event_map(rows)
        c1 = inject(SOURCE_SITE, year, events); c2 = inject(PUBLIC, year, events)
        print(f"{year}: 88 constellation centers; redundant alpha/beta observances removed; updated {c1} source + {c2} public pages")

if __name__ == "__main__": main()
