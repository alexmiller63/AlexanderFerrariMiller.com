#!/usr/bin/env python3
"""One-shot: update W17 bisect GOOD_REF to the recorded verified endpoint."""

from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path(".github/workflows/test-planet-finder-w17-historical-bisect.yml")
text = P.read_text(encoding="utf-8")

old = 'GOOD_REF: "6896c1aebc2438bdf424cceb8ec15a0bd6badb60"'
new = 'GOOD_REF: "95a9dd78fce7dd4044bee20a012b4ae88db8bfaa"'

if text.count(old) != 1:
    raise SystemExit(f"Safety stop: expected exactly one old GOOD_REF, found {text.count(old)}")

P.write_text(text.replace(old, new), encoding="utf-8")

me = Path(__file__)
source = me.read_text(encoding="utf-8")
arming_line = "ENABLED" + " = True"
lines = source.splitlines()
matches = [i for i, line in enumerate(lines) if line.strip() == arming_line]
if len(matches) != 1:
    raise SystemExit(f"Safety stop: arming line count={len(matches)}")
lines[matches[0]] = "ENABLED = False"
me.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("Updated W17 bisect GOOD_REF to 95a9dd78; Repair Once is OFF.")
