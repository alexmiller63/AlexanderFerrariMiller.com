#!/usr/bin/env python3
"""Deterministic white-box stress harness for Planet Finder search.

This deliberately puts every Solar-System body inside one zodiac sign so the
layout engine can be studied under severe crowding without astronomical input.
It calls the production search code; only the body longitudes are synthetic.
"""

from __future__ import annotations

import argparse
import os
import time

from planet_finder_geometry import (
    BODY_SYMBOLS, CANONICAL, FinderMode, RI,
    boxes_overlap, label_size, legal_candidate_positions,
    leader_hits_zodiac_rim, leaders_too_close, reserved_boxes, route, xy,
)
from planet_finder_search import layout, new_search_budget


def crowded_bodies(center: float = 15.0, span: float = 6.0):
    """Return all canonical bodies packed deterministically around one longitude."""
    if not 0.0 <= center < 360.0:
        raise ValueError("center must be in [0, 360)")
    if not 0.0 <= span < 30.0:
        raise ValueError("span must be in [0, 30) so all bodies remain in one sign")

    count = len(CANONICAL)
    if count == 1:
        longitudes = [center]
    else:
        start = center - span / 2.0
        step = span / (count - 1)
        longitudes = [start + i * step for i in range(count)]

    bodies = []
    for name, longitude in zip(CANONICAL, longitudes):
        key = name.lower()
        symbol = BODY_SYMBOLS[key]
        bodies.append((symbol, name, longitude % 360.0))
    return bodies


def first_level_forward_audit(mode: FinderMode, bodies, displacement_scale: float = 2.0, first_limit: int = 12):
    """Explain why a legal first placement is killed by one-step look-ahead.

    This intentionally mirrors production forward-check geometry but does not
    change production search state or consume its candidate budgets.
    """
    reserved = reserved_boxes(mode)
    print("WHITE BOX FORWARD AUDIT: first-level pruning", flush=True)

    for first_symbol, first_name, first_longitude in bodies:
        fw, fh = label_size(mode, first_name)
        first_anchor = xy(first_longitude, RI - 5)
        tested = 0
        print(f"FORWARD-AUDIT FIRST body={first_name}", flush=True)

        for _, _, first_box in legal_candidate_positions(
            first_longitude, fw, fh, reserved, displacement_scale
        ):
            first_path = route(
                first_anchor, (first_box.x, first_box.y), reserved,
                allow_initial_escape_count=3, prefix_cache={}
            )
            if first_path is None or leader_hits_zodiac_rim(first_path):
                continue
            tested += 1
            dead_body = None
            dead_counts = None

            for _, future_name, future_longitude in bodies:
                if future_name == first_name:
                    continue
                w, h = label_size(mode, future_name)
                anchor = xy(future_longitude, RI - 5)
                counts = {"raw": 0, "overlap": 0, "route": 0, "rim": 0, "leader": 0}
                witness = False
                for _, _, future_box in legal_candidate_positions(
                    future_longitude, w, h, reserved, displacement_scale
                ):
                    counts["raw"] += 1
                    if boxes_overlap(future_box, first_box, 14):
                        counts["overlap"] += 1
                        continue
                    path = route(
                        anchor, (future_box.x, future_box.y), [*reserved, first_box],
                        allow_initial_escape_count=3, prefix_cache={}
                    )
                    if path is None:
                        counts["route"] += 1
                        continue
                    if leader_hits_zodiac_rim(path):
                        counts["rim"] += 1
                        continue
                    if leaders_too_close(path, [first_path]):
                        counts["leader"] += 1
                        continue
                    witness = True
                    break
                if not witness:
                    dead_body = future_name
                    dead_counts = counts
                    break

            if dead_body is None:
                print(
                    f"  first-candidate={tested}: SURVIVES one-step forward check "
                    f"center=({first_box.x:.1f},{first_box.y:.1f})",
                    flush=True,
                )
                break
            print(
                f"  first-candidate={tested}: PRUNED by={dead_body} "
                f"center=({first_box.x:.1f},{first_box.y:.1f}) "
                f"raw={dead_counts['raw']} overlap={dead_counts['overlap']} "
                f"route={dead_counts['route']} rim={dead_counts['rim']} "
                f"leader={dead_counts['leader']}",
                flush=True,
            )
            if tested >= first_limit:
                break

        if tested == 0:
            print("  NO LEGAL FIRST PLACEMENT", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=[m.value for m in FinderMode], default="greek")
    parser.add_argument("--center", type=float, default=15.0,
                        help="center longitude; 15 degrees is the middle of Aries")
    parser.add_argument("--span", type=float, default=6.0,
                        help="total longitude span occupied by all bodies")
    parser.add_argument("--candidates", type=int, default=1)
    parser.add_argument("--body-cap", type=int, default=200)
    parser.add_argument("--seconds", type=float, default=180.0)
    parser.add_argument("--diagnostic", type=int, default=3)
    args = parser.parse_args()

    os.environ["PLANET_FINDER_DIAGNOSTIC_LEVEL"] = str(args.diagnostic)
    os.environ["PLANET_FINDER_MAX_NODE_CANDIDATES"] = str(args.body_cap)
    os.environ["PLANET_FINDER_MAX_SECONDS"] = str(args.seconds)

    mode = FinderMode(args.mode)
    bodies = crowded_bodies(args.center, args.span)
    print("WHITE BOX: all bodies deliberately crowded into one zodiac sign")
    print(f"mode={args.mode} center={args.center:g} span={args.span:g} candidates={args.candidates}")
    print("synthetic longitudes:")
    for symbol, name, longitude in bodies:
        print(f"  {name:8s} {symbol}  {longitude:8.3f}°")

    first_level_forward_audit(mode, bodies)

    budget = new_search_budget()
    started = time.monotonic()
    try:
        result = layout(
            mode,
            bodies,
            target_solutions=args.candidates,
            budget=budget,
            context_label="WHITE-BOX-CROWDED",
        )
    except Exception as exc:
        elapsed = time.monotonic() - started
        print(f"WHITE BOX RESULT: FAILURE after {elapsed:.3f}s: {type(exc).__name__}: {exc}")
        raise

    elapsed = time.monotonic() - started
    print(f"WHITE BOX RESULT: SUCCESS after {elapsed:.3f}s; placements={len(result)}")


if __name__ == "__main__":
    main()
