#!/usr/bin/env python3
"""One-shot: restore the coordinated-geometry function boundary."""

from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

P = Path("tools/planet_finder_search_core.py")
text = P.read_text(encoding="utf-8")

start_marker = (
    "        # Conjunctions have no placement path of their own.  Every body enters\n"
)

end_marker = (
    "\n    try:\n"
    "        solved = search_coordinated_geometry()"
)

search_start = text.find("    def search(depth):")
if search_start < 0:
    raise SystemExit("Safety stop: def search(depth) not found")

start = text.find(start_marker, search_start)
end = text.find(end_marker, start)

if start < 0 or end < 0:
    raise SystemExit(
        f"Safety stop: coordinated-geometry anchors not found "
        f"(start={start}, end={end})"
    )

if "    def search_coordinated_geometry():" in text:
    raise SystemExit(
        "Safety stop: search_coordinated_geometry() already exists"
    )

misplaced_body = text[start:end]

# Move the existing coordinated-alignment block beneath its proper
# function boundary without otherwise changing that block.
indented_body = "".join(
    ("    " + line) if line.strip() else line
    for line in misplaced_body.splitlines(True)
)

wrapper = (
    "    def search_coordinated_geometry():\n"
    "        # Forensic mode bypasses only the speculative preplanner.\n"
    "        # Recursive alignment DFS/backtracking remains active.\n"
    "        if os.environ.get("
    "\"PLANET_FINDER_SKIP_ALIGNMENT_PREPLANNER\", \"0\""
    ") == \"1\":\n"
    "            alignment_names = [\n"
    "                [item[1][1] for item in group]\n"
    "                for group in alignment_group_items\n"
    "            ]\n"
    "            diagnostic_print(\n"
    "                f\"Planet Finder {mode}: "
    "FORENSIC ALIGNMENT-PREPLANNER BYPASS \"\n"
    "                f\"alignment_groups={alignment_names} \"\n"
    "                f\"staged={len(staged)} placed={len(placed)} "
    "leaders={len(leaders)}\",\n"
    "                flush=True,\n"
    "            )\n"
    "            if alignment_group_items:\n"
    "                return solve_alignment_group(0)\n"
    "            return search(0)\n"
    "\n"
    + indented_body
)

text = text[:start] + wrapper + text[end:]
P.write_text(text, encoding="utf-8")

# Self-disable after a successful repair.  Match the assignment including
# its surrounding newlines so text elsewhere in this script cannot count.
me = Path(__file__)
source = me.read_text(encoding="utf-8")

enabled_assignment = "\nENABLED = " + "True\n"
disabled_assignment = "\nENABLED = False\n"

if source.count(enabled_assignment) != 1:
    raise SystemExit(
        "Safety stop: ENABLED assignment not uniquely identifiable"
    )

source = source.replace(
    enabled_assignment,
    disabled_assignment,
    1,
)

me.write_text(source, encoding="utf-8")

print(
    "Restored search_coordinated_geometry(); "
    "Repair Once is now OFF."
)