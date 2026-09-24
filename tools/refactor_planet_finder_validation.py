#!/usr/bin/env python3
"""Safely extract completed-layout validation from Planet Finder generator."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "tools" / "generate_planet_finders.py"
MOD = ROOT / "tools" / "planet_finder_validation.py"
START = "def validate_layout(mode: str, result) -> tuple[bool, list[str]]:\n"
END = "\n\ndef polyline(points):"
IMPORT_ANCHOR = "from planet_finder_search import DepthNodeBudgetExhausted, SearchOutcome\n"
IMPORT = "from planet_finder_validation import validate_layout\n"
PRELUDE = '''"""Independent completed-layout validation for Planet Finder."""\nfrom __future__ import annotations\n\nimport math\n\nfrom planet_finder_geometry import (\n    CX, CY, RI, LABEL_RIM_CLEARANCE, LABEL_COLLISION_PADDING,\n    IMMUTABLE_LEADER_CLEARANCE, PLACED_LABEL_LEADER_CLEARANCE,\n    reserved_boxes, boxes_overlap, segment_hits_box,\n    leader_hits_zodiac_rim, leaders_too_close,\n)\n\n'''

def main():
    text = GEN.read_text(encoding="utf-8")
    if IMPORT in text:
        if not MOD.exists():
            raise SystemExit("validation import exists but module is missing")
        print("validation extraction already applied")
        return
    if MOD.exists():
        raise SystemExit("validation module already exists; refusing ambiguous rewrite")
    a = text.find(START)
    b = text.find(END, a)
    if a < 0 or b < 0:
        raise SystemExit("validation boundaries not found")
    block = text[a:b]
    if "return not errors, errors" not in block:
        raise SystemExit("validation block incomplete")
    MOD.write_text(PRELUDE + block + "\n", encoding="utf-8")
    rewritten = text[:a] + text[b + 2:]
    if IMPORT_ANCHOR not in rewritten:
        raise SystemExit("import anchor missing")
    rewritten = rewritten.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT, 1)
    GEN.write_text(rewritten, encoding="utf-8")
    print(f"extracted {block.count(chr(10)) + 1} validation lines")

if __name__ == "__main__":
    main()
