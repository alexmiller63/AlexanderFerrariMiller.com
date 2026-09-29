#!/usr/bin/env python3
"""One-shot repair: conjunction classification must not alter alignment geometry."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_geometry.py")
text = TARGET.read_text(encoding="utf-8")

old = '''def alignment_groups(bodies, threshold: float = ALIGNMENT_DEGREES):
    """Return deterministic broad alignment groups after conjunction removal.

    Near-conjunction members are deliberately excluded: they belong to the
    earlier, more constrained placement phase and will already be frozen before
    alignment placement begins. Remaining connected circular-lambda neighbors
    within ``threshold`` form an alignment group.
    """
    conjunction_names = {
        item[1]
        for group in conjunction_groups(bodies)
        for item in group
    }
    remaining = [item for item in bodies if item[1] not in conjunction_names]
    return conjunction_groups(remaining, threshold=threshold)
'''
new = '''def alignment_groups(bodies, threshold: float = ALIGNMENT_DEGREES):
    """Return deterministic broad alignment groups.

    Conjunction status changes backtracking granularity only. It must never
    remove bodies from, split, or otherwise alter the ordinary coordinated
    alignment geometry. Therefore alignment grouping is computed directly
    from the complete body population at the alignment threshold.
    """
    return conjunction_groups(bodies, threshold=threshold)
'''

if text.count(old) != 1:
    raise SystemExit("Safety stop: conjunction-removing alignment_groups did not match exactly once")
text = text.replace(old, new, 1)
TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "alignment_groups no longer removes conjunction members. Conjunctions now "
    "participate in the same ordinary alignment geometry at every separation; "
    "conjunction classification is reserved for backtracking atomicity. "
    "Repair Once is now OFF."
)
