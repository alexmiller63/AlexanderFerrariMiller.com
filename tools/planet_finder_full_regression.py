#!/usr/bin/env python3
"""Read-only real-ephemeris Planet Finder regression for every ISO week of 2026."""
import argparse
import csv
import json
import sys
import time
import traceback
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from star_almanack_ephemeris import StarAlmanackEphemeris
from populate_ephemeris_planet_finder_by_date import calculate_year, finder_bodies
from planet_finder_geometry import FinderMode, label_size, CANONICAL
from planet_finder_search import layout, new_search_budget
from planet_finder_validation import validate_layout

MODES = (("greek", FinderMode.GREEK), ("english", FinderMode.ENGLISH), ("mixed", FinderMode.MIXED))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-week", type=int, default=1)
    parser.add_argument("--end-week", type=int, default=53)
    args = parser.parse_args()
    if not 1 <= args.start_week <= args.end_week <= 53:
        parser.error("Expected 1 <= start-week <= end-week <= 53")
    output = ROOT / "generated" / "planet-finder-regression"
    output.mkdir(parents=True, exist_ok=True)
    # Measure a shared label envelope before executing any notation mode.
    # Measurement alone does not guarantee a feasible placement.
    reservations = {}
    for name in CANONICAL:
        sizes = {label: label_size(mode, name) for label, mode in MODES}
        reservations[name] = {
            "width": max(size[0] for size in sizes.values()),
            "height": max(size[1] for size in sizes.values()),
            "by_mode": sizes,
        }
    (output / "cross-mode-space-requirements.json").write_text(
        json.dumps(reservations, indent=2) + "\n", encoding="utf-8"
    )
    print("Cross-mode space envelopes measured; placement feasibility not yet established.", flush=True)
    results = []
    try:
        generated = calculate_year(2026, StarAlmanackEphemeris())
    except Exception:
        (output / "setup-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    total = date(2026, 12, 28).isocalendar().week
    for week in range(args.start_week, min(args.end_week, total) + 1):
        bodies = finder_bodies(generated, week)
        for label, mode in MODES:
            started = time.monotonic()
            row = {"week": f"2026-W{week:02d}", "mode": label, "status": "FAIL", "seconds": 0, "error": ""}
            try:
                solution = layout(mode, bodies, budget=new_search_budget(), context_label=f"regression 2026-W{week:02d} {label}")
                valid, errors = validate_layout(mode, solution)
                if not valid:
                    raise AssertionError("; ".join(errors))
                row["status"] = "PASS"
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
                (output / f"W{week:02d}-{label}-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            finally:
                row["seconds"] = round(time.monotonic() - started, 3)
                results.append(row)
                print(f'{len(results)}/{(min(args.end_week, total)-args.start_week+1)*3} {row["week"]} {label} {row["status"]} {row["seconds"]}s {row["error"]}', flush=True)
                with (output / "results.csv").open("w", newline="", encoding="utf-8") as file:
                    writer = csv.DictWriter(file, fieldnames=list(row))
                    writer.writeheader()
                    writer.writerows(results)
                (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    failures = sum(r["status"] != "PASS" for r in results)
    (output / "summary.txt").write_text(f"Total: {len(results)}; passed: {len(results)-failures}; failed: {failures}\n", encoding="utf-8")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
