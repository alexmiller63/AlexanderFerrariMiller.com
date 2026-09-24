"""Diagnostic-only leader tracing used by the White Box Planet Finder.

This module does not alter placement legality.  It wraps the production
minimum-separation calculation and records representative zero-distance
segment pairs so we can distinguish genuine crossings from geometry artifacts.
"""
from __future__ import annotations

import os

from planet_finder_geometry import minimum_leader_separation as _minimum

_TRACE_LIMIT = 40
_trace_count = 0


def _fmt_path(path):
    return " -> ".join(f"({x:.3f},{y:.3f})" for x, y in path)


def traced_minimum_leader_separation(path, existing_paths):
    global _trace_count
    best, pair = _minimum(path, existing_paths)
    try:
        level = int(os.environ.get("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0"))
    except ValueError:
        level = 0
    if level >= 3 and pair is not None and best <= 1e-9 and _trace_count < _TRACE_LIMIT:
        oi, proposed_segment, existing_segment = pair
        other = existing_paths[oi]
        a, b = path[proposed_segment], path[proposed_segment + 1]
        c, d = other[existing_segment], other[existing_segment + 1]
        _trace_count += 1
        print(
            f"ZERO-DISTANCE-LEADER #{_trace_count} "
            f"proposed_segment={proposed_segment} existing_path={oi} "
            f"existing_segment={existing_segment}",
            flush=True,
        )
        print(f"  proposed_path={_fmt_path(path)}", flush=True)
        print(f"  existing_path={_fmt_path(other)}", flush=True)
        print(
            "  segment_pair="
            f"A({a[0]:.6f},{a[1]:.6f})->B({b[0]:.6f},{b[1]:.6f}) "
            f"C({c[0]:.6f},{c[1]:.6f})->D({d[0]:.6f},{d[1]:.6f})",
            flush=True,
        )
    return best, pair
