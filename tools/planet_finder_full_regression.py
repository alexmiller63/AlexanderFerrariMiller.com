#!/usr/bin/env python3
"""Read-only real-ephemeris Planet Finder regression for every ISO week of 2026."""
import argparse
import csv
import json
import re
import sys
import time
import traceback
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from star_almanack_ephemeris import StarAlmanackEphemeris
from populate_ephemeris_planet_finder_by_date import calculate_year, finder_bodies
from planet_finder_geometry import FinderMode
from planet_finder_search import layout, new_search_budget
from planet_finder_validation import validate_layout

MODES = (("greek", FinderMode.GREEK), ("english", FinderMode.ENGLISH), ("mixed", FinderMode.MIXED))

def write_reports(output, results):
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["week", "mode", "status", "seconds", "error"])
        writer.writeheader()
        writer.writerows(results)
    (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    passed = sum(r["status"] == "PASS" for r in results)
    failed = sum(r["status"] == "FAIL" for r in results)
    unfinished = len(results) - passed - failed
    summary = f"Total: {len(results)}; passed: {passed}; failed: {failed}; unfinished: {unfinished}\n"
    (output / "summary.txt").write_text(summary, encoding="utf-8")
    lines = ["## Planet Finder regression", "", summary.strip(), "",
             "RUNNING or PENDING entries are unfinished, not passes.", "",
             "| Week | Mode | Result | Seconds |", "| --- | --- | --- | ---: |"]
    lines.extend(f'| {r["week"]} | {r["mode"]} | {r["status"]} | {r["seconds"]} |' for r in results)
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-week", type=int, default=1)
    parser.add_argument("--end-week", type=int, default=53)
    parser.add_argument("--weeks", help="Comma-separated ISO weeks; overrides start/end week")
    args = parser.parse_args()
    if args.weeks is not None:
        if not re.fullmatch(r"\s*\d{1,2}(?:\s*,\s*\d{1,2})*\s*", args.weeks):
            parser.error("Enter comma-separated week numbers, e.g. 17,20,25,39")
        weeks = list(dict.fromkeys(int(w.strip()) for w in args.weeks.split(",")))
        if any(w < 1 or w > 53 for w in weeks):
            parser.error("Weeks must be 1 through 53")
    else:
        if not 1 <= args.start_week <= args.end_week <= 53:
            parser.error("Expected 1 <= start-week <= end-week <= 53")
        total = date(2026, 12, 28).isocalendar().week
        weeks = list(range(args.start_week, min(args.end_week, total) + 1))
    output = ROOT / "generated" / "planet-finder-regression"
    output.mkdir(parents=True, exist_ok=True)
    for old in list(output.glob("W??-*-error.txt")) + [output / "setup-error.txt"]:
        old.unlink(missing_ok=True)
    results = [{"week": f"2026-W{week:02d}", "mode": label, "status": "PENDING",
                "seconds": 0, "error": ""} for week in weeks for label, _ in MODES]
    write_reports(output, results)
    try:
        generated = calculate_year(2026, StarAlmanackEphemeris())
    except Exception:
        (output / "setup-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    for index, row in enumerate(results, 1):
        week = int(row["week"][-2:])
        label = row["mode"]
        mode = dict(MODES)[label]
        started = time.monotonic()
        row["status"] = "RUNNING"
        write_reports(output, results)
        print(f'{index}/{len(results)} {row["week"]} {label} START', flush=True)
        try:
            bodies = finder_bodies(generated, week)
            solution = layout(mode, bodies, budget=new_search_budget(), context_label=f"regression 2026-W{week:02d} {label}")
            valid, errors = validate_layout(mode, solution)
            if not valid:
                raise AssertionError("; ".join(errors))
            row["status"] = "PASS"
        except Exception as exc:
            row["status"] = "FAIL"
            row["error"] = f"{type(exc).__name__}: {exc}"
            (output / f"W{week:02d}-{label}-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        finally:
            row["seconds"] = round(time.monotonic() - started, 3)
            write_reports(output, results)
            print(f'{index}/{len(results)} {row["week"]} {label} {row["status"]} {row["seconds"]}s {row["error"]}', flush=True)
    print((output / "summary.txt").read_text(encoding="utf-8"), flush=True)
    return 1 if any(r["status"] != "PASS" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
