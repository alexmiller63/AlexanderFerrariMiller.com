#!/usr/bin/env python3
"""One-shot: repair literal newline escapes in the alignment cap edit."""

from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")

marker = "        # Keep a dead final alignment member from monopolizing the mode clock."
start = text.find(marker)
end = text.find("        diagnostic_print(", start)
if start < 0 or end < 0 or text.find(marker, start + 1) >= 0:
    raise SystemExit("Safety stop: malformed alignment-cap block missing or non-unique")

block = text[start:end]
if "\\n" not in block:
    raise SystemExit("Safety stop: expected literal newline escapes are absent")

fixed = block.replace("\\n", "\n")
if 'candidate_limit = min(budget["max_node_candidates"], 200)' not in fixed:
    raise SystemExit("Safety stop: 200-choice cap missing from repaired block")

P.write_text(text[:start] + fixed + text[end:], encoding="utf-8")

me = Path(__file__)
source = me.read_text(encoding="utf-8")
arming_line = "ENABLED" + " = True"
lines = source.splitlines()
matches = [i for i, line in enumerate(lines) if line.strip() == arming_line]
if len(matches) != 1:
    raise SystemExit(f"Safety stop: arming line count={len(matches)}")
lines[matches[0]] = "ENABLED = False"
me.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("Repaired literal newline escapes in alignment cap edit; Repair Once is OFF.")
