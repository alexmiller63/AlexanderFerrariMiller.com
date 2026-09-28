#!/usr/bin/env python3
"""Repair-once: correct global leader/rim geometry.

A leader anchor intentionally begins in the protected rim band.  Permit only the
initial inward escape from that band.  Once the path has entered the protected
interior, every remaining vertex must stay there; a later outward excursion is
still rejected.
"""
from pathlib import Path

TARGET = Path("tools/planet_finder_geometry.py")
text = TARGET.read_text(encoding="utf-8")

old = '''def leader_hits_zodiac_rim(path, clearance: float = LEADER_RIM_CLEARANCE) -> bool:\n    """Reject a leader that touches or crosses the inner zodiac rim.\n\n    The inner chart is a convex disk, so a polyline remains clear of the\n    circular rim exactly when every vertex remains inside the protected\n    radius.  The body's anchor is at RI-5 and is therefore legal; elbows that\n    wander out to the rim are not.\n    """\n    limit = RI - clearance\n    return any(math.hypot(x - CX, y - CY) >= limit for x, y in path)\n'''

new = '''def leader_hits_zodiac_rim(path, clearance: float = LEADER_RIM_CLEARANCE) -> bool:\n    """Reject a leader that returns to/crosses the protected zodiac rim.\n\n    Body anchors intentionally start near the inner zodiac rim and may lie\n    inside its clearance band.  Permit that contiguous initial band only while\n    the leader escapes inward.  After the path first reaches the protected\n    interior, it may never leave it again.  Because the protected interior is\n    a convex disk, endpoints inside it imply the whole intervening segment is\n    inside it as well.\n    """\n    limit = RI - clearance\n    radii = [math.hypot(x - CX, y - CY) for x, y in path]\n    entered_interior = False\n    previous_radius = None\n    for radius in radii:\n        if radius < limit:\n            entered_interior = True\n        elif entered_interior:\n            return True\n        elif previous_radius is not None and radius > previous_radius + 1e-9:\n            # Before entering the protected interior, the initial escape must\n            # move monotonically inward rather than wander outward along/rimward.\n            return True\n        previous_radius = radius\n    return False\n'''

count = text.count(old)
if count != 1:
    raise SystemExit(f"Refusing repair: expected leader_hits_zodiac_rim implementation exactly once, found {count}")
TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Applied global initial-inward leader rim escape correction.")
