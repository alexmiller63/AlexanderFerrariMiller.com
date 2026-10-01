#!/usr/bin/env python3
"""One-shot: remove the two legacy inner max_seconds termination blocks."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")

# Remove candidate-generation wall-clock block, preserving stats["started"].
anchor1 = '            run_elapsed = now - started\n            if run_elapsed >= budget["max_seconds"]:\n'
start1 = text.find(anchor1)
end1 = text.find('            stats["started"] = True\n', start1)
if start1 < 0 or end1 < 0:
    raise SystemExit(f"Safety stop: candidate clock anchors start={start1} end={end1}")
text = text[:start1] + text[end1:]

# Remove DFS wall-clock block, preserving deterministic node accounting.
anchor2 = '        run_elapsed = now - started\n        if run_elapsed >= budget["max_seconds"]:\n'
search_start = text.find('    def search(depth):')
start2 = text.find(anchor2, search_start)
end2 = text.find('        nodes += 1\n', start2)
if search_start < 0 or start2 < 0 or end2 < 0:
    raise SystemExit(f"Safety stop: DFS clock anchors search={search_start} start={start2} end={end2}")
text = text[:start2] + text[end2:]

P.write_text(text, encoding="utf-8")
me = Path(__file__)
me.write_text(me.read_text(encoding="utf-8").replace("ENABLED = True", "ENABLED = False", 1), encoding="utf-8")
print("Removed both legacy inner max_seconds termination checks; deterministic limits and controller hard fuse remain. Repair Once is now OFF.")
