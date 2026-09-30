#!/usr/bin/env python3
"""One-shot diagnostic repair: print exact W36 Venus blocker attribution.

Adds reporting only. Candidate generation, geometry, ordering, budgets, and
production decisions are unchanged. Repair Once self-disables.
"""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

CORE = Path("tools/planet_finder_search_core.py")
core = CORE.read_text(encoding="utf-8")

old = '''        diagnostic_print(
            f"Planet Finder {mode}: TERMINAL REJECTION CONSTRAINTS "
            + " ".join(f"{key}={count:,}" for key, count in ranked),
            flush=True,
        )
        diagnostic_print(
            f"Planet Finder {mode}: TERMINAL BEST-PARTIAL deepest={deepest}/{len(order)}",
            flush=True,
        )
'''

new = '''        diagnostic_print(
            f"Planet Finder {mode}: TERMINAL REJECTION CONSTRAINTS "
            + " ".join(f"{key}={count:,}" for key, count in ranked),
            flush=True,
        )

        # Diagnostic-only W36 attribution: identify which already-placed
        # alignment labels/leaders most often prevent Venus from becoming a
        # viable ordinary-body placement.  These counters are observational
        # only and never participate in search decisions.
        venus_attribution = {
            "overlap": {},
            "existing-leader": {},
            "leader-graze": {},
        }
        venus_own_graze = 0
        for (diag_depth, diag_name), stats in diagnostic_stats.items():
            if diag_name != "Venus":
                continue
            venus_own_graze += stats.get("own_label_graze", 0)
            for label, count in stats.get("overlap_by_label", {}).items():
                venus_attribution["overlap"][label] = venus_attribution["overlap"].get(label, 0) + count
            for label, count in stats.get("existing_leader_by_name", {}).items():
                venus_attribution["existing-leader"][label] = venus_attribution["existing-leader"].get(label, 0) + count
            for label, count in stats.get("leader_graze_by_name", {}).items():
                venus_attribution["leader-graze"][label] = venus_attribution["leader-graze"].get(label, 0) + count
        for kind, counts in venus_attribution.items():
            top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:12]
            diagnostic_print(
                f"Planet Finder {mode}: VENUS BLOCKERS kind={kind} "
                + (" ".join(f"{name}={count:,}" for name, count in top) if top else "none"),
                flush=True,
            )
        diagnostic_print(
            f"Planet Finder {mode}: VENUS BLOCKERS kind=own-label-graze count={venus_own_graze:,}",
            flush=True,
        )
        diagnostic_print(
            f"Planet Finder {mode}: TERMINAL BEST-PARTIAL deepest={deepest}/{len(order)}",
            flush=True,
        )
'''

if core.count(old) != 1:
    raise SystemExit(f"Safety stop: diagnostic anchor count={core.count(old)}; expected 1")
CORE.write_text(core.replace(old, new, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print("Added Venus blocker-attribution summary diagnostics. Repair Once is now OFF.")
