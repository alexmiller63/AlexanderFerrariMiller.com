#!/usr/bin/env python3
"""One-shot repair: make wide-first intrinsic to coordinated placement."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

# The shared coordinated planner must not discard the wide end of the search
# before it starts.  This ordering is shared by close ordinary alignments and
# conjunction blobs: widest displacement first, progressively narrower after
# wider geometry fails.
old = '''            options.sort(key=lambda row: math.hypot(row[0] - natural[0], row[1] - natural[1]))
            pools[name] = options[:80]
'''
new = '''            # Wide-first is a planner invariant, not conjunction-specific
            # behavior.  Keep the widest legal alternatives in the bounded
            # pool and try them before progressively narrower placements.
            options.sort(
                key=lambda row: math.hypot(row[0] - natural[0], row[1] - natural[1]),
                reverse=True,
            )
            pools[name] = options[:80]
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: coordinated candidate ordering did not match exactly once")
text = text.replace(old, new, 1)

TARGET.write_text(text, encoding="utf-8")

# Self-disarm after successful rewrite.
me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Shared coordinated placement now keeps and tries wide candidates first, "
    "then progressively narrower candidates. Collision, routing, circular-lambda "
    "ordering, and conjunction atomicity are unchanged. Repair Once is now OFF."
)
