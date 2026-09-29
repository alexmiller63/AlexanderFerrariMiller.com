#!/usr/bin/env python3
"""One-shot diagnostic: emit Sun immutable candidate divergence at 2deg/1deg."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old = '''            options = [
                row for row in legal_candidate_positions(
                    longitude, w, h, reserved, displacement_scale
                )
                if not any(boxes_overlap(row[2], box, LABEL_COLLISION_PADDING) for box in placed)
                and not any(segment_hits_box(path[i], path[i + 1], row[2], 10)
                            for path in leaders for i in range(len(path) - 1))
            ]
'''
new = '''            immutable_diag = {} if name == "Sun" and abs(longitude - 101.0) < 1e-9 else None
            options = [
                row for row in legal_candidate_positions(
                    longitude, w, h, reserved, displacement_scale, immutable_diag
                )
                if not any(boxes_overlap(row[2], box, LABEL_COLLISION_PADDING) for box in placed)
                and not any(segment_hits_box(path[i], path[i + 1], row[2], 10)
                            for path in leaders for i in range(len(path) - 1))
            ]
            if immutable_diag is not None:
                trace = immutable_diag.get("sun_1deg_first_candidate_trace")
                diagnostic_print(
                    f"Planet Finder {mode}: SUN 1DEG FIRST-CANONICAL {trace}",
                    flush=True,
                )
                audit = immutable_diag.get("immutable_candidate_audit", [])
                natural_trace = xy(longitude, PREFERRED_LABEL_RADII[0])
                rejected = sorted(
                    audit,
                    key=lambda row: math.hypot(row[0] - natural_trace[0], row[1] - natural_trace[1]),
                    reverse=True,
                )[:12]
                diagnostic_print(
                    f"Planet Finder {mode}: SUN 1DEG WIDEST-IMMUTABLE-REJECTS " + ";".join(
                        f"x={x:.3f},y={y:.3f},d={math.hypot(x-natural_trace[0], y-natural_trace[1]):.3f},reason={reason},hits={hits}"
                        for x, y, reason, hits in rejected
                    ),
                    flush=True,
                )
'''

if text.count(old) != 1:
    raise SystemExit("Safety stop: alignment option construction did not match exactly once")
text = text.replace(old, new, 1)
TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Added direct Sun 1deg candidate trace: first canonical fate plus widest immutable rejects. "
    "No geometry, legality, ordering, or search behavior changed. Repair Once is now OFF."
)
