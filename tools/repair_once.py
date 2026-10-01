#!/usr/bin/env python3
"""One-shot: remove legacy inner wall-clock termination checks.

Deterministic node/candidate limits decide search termination.  The controller's
hard wall-clock fuse remains the sole emergency watchdog.
"""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")

start = text.index('            run_elapsed = now - started\n            if run_elapsed >= budget["max_seconds"]:', text.index("def candidates_for"))
end = text.index('            stats["started"] = True', start)
text = text[:start] + text[end:]

start = text.index('        run_elapsed = now - started\n        if run_elapsed >= budget["max_seconds"]:', text.index("def search(depth):"))
end = text.index('        nodes += 1', start)
text = text[:start] + text[end:]

P.write_text(text, encoding="utf-8")

me = Path(__file__)
me.write_text(me.read_text(encoding="utf-8").replace("ENABLED = True", "ENABLED = False", 1), encoding="utf-8")
print("Removed both legacy inner max_seconds termination checks. Controller hard fuse remains. Repair Once is now OFF.")
