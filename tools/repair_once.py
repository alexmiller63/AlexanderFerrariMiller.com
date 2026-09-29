#!/usr/bin/env python3
"""One-shot diagnostic: split candidate rejection causes at the 1.8/1.7 cliff."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old_own = '''            if own_label_bad:
                rejected_leader += 1
                stats["leader"] += 1
                stats["leader_graze"] += 1
                continue
'''
new_own = '''            if own_label_bad:
                if os.environ.get("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF") == "1" and name in ("Venus", "Sun"):
                    diagnostic_print(
                        f"Planet Finder {mode}: CANDIDATE LEGALITY body={name} "
                        f"stage=own-label result=REJECT route_backtracks={route_backtracks} "
                        f"box=({box.x:.1f},{box.y:.1f},{box.w:.1f},{box.h:.1f}) "
                        f"path={[(round(px,1), round(py,1)) for px,py in rendered_path]}",
                        level=1, flush=True,
                    )
                rejected_leader += 1
                stats["leader"] += 1
                stats["leader_graze"] += 1
                continue
'''
if text.count(old_own) != 1:
    raise SystemExit("Safety stop: own-label rejection block did not match exactly once")
text = text.replace(old_own, new_own, 1)

old_close = '''            if too_close:
                rejected_leader += 1
                stats["leader"] += 1
                stats["leader_graze"] += 1
                continue
            # Diagnostic-only geometry signature.  Round below rendering
'''
new_close = '''            if too_close:
                if os.environ.get("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF") == "1" and name in ("Venus", "Sun"):
                    diagnostic_print(
                        f"Planet Finder {mode}: CANDIDATE LEGALITY body={name} "
                        f"stage=leader-to-leader result=REJECT "
                        f"box=({box.x:.1f},{box.y:.1f},{box.w:.1f},{box.h:.1f}) "
                        f"path={[(round(px,1), round(py,1)) for px,py in path]} "
                        f"prior_paths={[[ (round(px,1), round(py,1)) for px,py in prior] for prior in leaders]}",
                        level=1, flush=True,
                    )
                rejected_leader += 1
                stats["leader"] += 1
                stats["leader_graze"] += 1
                continue
            if os.environ.get("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF") == "1" and name in ("Venus", "Sun"):
                diagnostic_print(
                    f"Planet Finder {mode}: CANDIDATE LEGALITY body={name} stage=viability result=ACCEPT "
                    f"box=({box.x:.1f},{box.y:.1f},{box.w:.1f},{box.h:.1f}) "
                    f"path={[(round(px,1), round(py,1)) for px,py in path]}",
                    level=1, flush=True,
                )
            # Diagnostic-only geometry signature.  Round below rendering
'''
if text.count(old_close) != 1:
    raise SystemExit("Safety stop: leader-too-close rejection block did not match exactly once")
text = text.replace(old_close, new_close, 1)
TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Added diagnostic-only candidate-legality tracing for Venus/Sun: "
    "own-label rejection vs leader-to-leader rejection vs accepted viability. "
    "No solver geometry or acceptance behavior changed. Repair Once is now OFF."
)
