#!/usr/bin/env python3
"""One-shot: make alignment MRV ranking use cheap geometry domains."""

from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")

old = '''            probe = alignment_profiled_candidates(
                candidate_item, diagnostic_depth, "alignment-rank"
            )
            count = 0
            cutoff = False
            try:
                for _ in probe:
                    count += 1
                    # Compare every alignment member against the same fixed
                    # bound. Cross-body early cutoff makes later domain counts
                    # incomparable and can choose the wrong MRV member.
                    if count >= budget["max_node_candidates"]:
                        cutoff = True
                        break
            finally:
                probe.close()
'''

new = '''            # MRV is only a search-order heuristic. Rank on the cheap
            # necessary-condition geometry domain instead of exhaustively
            # routing every candidate for every remaining member. Exact routed
            # viability is still authoritative when the chosen member is
            # explored below, so this changes cost/order but not correctness.
            probe = alignment_geometry_candidates(candidate_item)
            count = 0
            cutoff = False
            try:
                for _ in probe:
                    count += 1
                    if count >= budget["max_node_candidates"]:
                        cutoff = True
                        break
            finally:
                probe.close()
'''

if text.count(old) != 1:
    raise SystemExit("Safety stop: alignment ranking block missing or non-unique")
text = text.replace(old, new, 1)
P.write_text(text, encoding="utf-8")

me = Path(__file__)
source = me.read_text(encoding="utf-8")
needle = "\nENABLED = True\n"
if source.count(needle) != 1:
    raise SystemExit("Safety stop: ENABLED assignment not unique")
me.write_text(source.replace(needle, "\nENABLED = False\n", 1), encoding="utf-8")
print("Installed cheap-geometry alignment MRV ranking; Repair Once is OFF.")
