#!/usr/bin/env python3
"""One-shot: remove redundant same-blob alignment forward look-ahead.

The authoritative recursive alignment DFS already proves these continuations.
Removing the speculative existence probes changes pruning only, not placement
legality, candidate order, or the set of accepted complete layouts.
"""

from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")

start_marker = """                # Conservative same-blob forward checking.  After this
"""
end_marker = """                # Do not run the ordinary-body pair proof here.  It is a
"""

if text.count(start_marker) != 1 or text.count(end_marker) != 1:
    raise SystemExit(
        "Safety stop: expected one same-blob forward-check block "
        f"(start={text.count(start_marker)}, end={text.count(end_marker)})"
    )

start = text.index(start_marker)
end = text.index(end_marker, start)
replacement = """                # Do not speculatively forward-probe remaining alignment
                # members here. The recursive alignment DFS immediately below
                # performs the same routed continuation authoritatively. W17
                # diagnostics showed these redundant existence probes dominated
                # the mode clock (especially Moon alignment-forward). Removing
                # them changes pruning only, not geometry or accepted layouts.
"""
text = text[:start] + replacement + text[end:]
P.write_text(text, encoding="utf-8")

me = Path(__file__)
source = me.read_text(encoding="utf-8")
arming_line = "ENABLED" + " = True"
lines = source.splitlines()
matches = [i for i, line in enumerate(lines) if line.strip() == arming_line]
if len(matches) != 1:
    raise SystemExit(f"Safety stop: arming line count={len(matches)}")
lines[matches[0]] = "ENABLED = False"
me.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("Removed redundant alignment-forward look-ahead; Repair Once is OFF.")
