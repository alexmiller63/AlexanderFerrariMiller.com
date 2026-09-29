#!/usr/bin/env python3
"""One-shot diagnostic: expose why 2-degree geometry stops working at 1 degree."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old = '''        result = assign(order_names, pools, {})
        planned = result[0] if result else {}
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT PREPLACEMENT "
            f"planned={len(planned)}/{len(order_names)} nodes={nodes}",
            flush=True,
        )
        return result
'''
new = '''        # Diagnostic fingerprint for the Venus/Sun threshold ladder.  Report
        # the widest generated candidates before DFS so 2deg and 1deg can be
        # compared without changing candidate generation or search order.
        if "Venus" in pools and "Sun" in pools:
            for diagnostic_name in ("Venus", "Sun"):
                natural = xy(longitudes[diagnostic_name], PREFERRED_LABEL_RADII[0])
                diagnostic_rows = pools[diagnostic_name][:5]
                diagnostic_print(
                    f"Planet Finder {mode}: ALIGNMENT POOL {diagnostic_name} "
                    f"count={len(pools[diagnostic_name])} widest=" + ";".join(
                        f"x={row[0]:.3f},y={row[1]:.3f},"
                        f"d={math.hypot(row[0]-natural[0], row[1]-natural[1]):.3f}"
                        for row in diagnostic_rows
                    ),
                    flush=True,
                )

        result = assign(order_names, pools, {})
        planned = result[0] if result else {}
        diagnostic_print(
            f"Planet Finder {mode}: ALIGNMENT PREPLACEMENT "
            f"planned={len(planned)}/{len(order_names)} nodes={nodes}",
            flush=True,
        )
        if result is not None and "Venus" in planned and "Sun" in planned:
            for diagnostic_name in ("Venus", "Sun"):
                row = planned[diagnostic_name]
                path = result[1].get(diagnostic_name, ())
                diagnostic_print(
                    f"Planet Finder {mode}: ALIGNMENT WINNER {diagnostic_name} "
                    f"x={row[0]:.3f} y={row[1]:.3f} "
                    f"path=" + "->".join(f"({px:.3f},{py:.3f})" for px, py in path),
                    flush=True,
                )
        return result
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: alignment result block did not match exactly once")
text = text.replace(old, new, 1)
TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Added diagnostic-only Venus/Sun alignment pool and winning-geometry fingerprints. "
    "No geometry, candidate ordering, collision rule, or search behavior changed. "
    "Repair Once is now OFF."
)
