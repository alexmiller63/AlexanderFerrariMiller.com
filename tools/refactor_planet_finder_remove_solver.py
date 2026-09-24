#!/usr/bin/env python3
"""Safely migrate the Planet Finder DFS solver into search support."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
GEN=ROOT/"tools"/"generate_planet_finders.py"
MOD=ROOT/"tools"/"planet_finder_search.py"
START="def _solve_order("
END="\ndef generate_week(year: int, week: int):"
def main():
    gen=GEN.read_text(encoding="utf-8")
    mod=MOD.read_text(encoding="utf-8")
    if "def _solve_order(" in mod:
        raise SystemExit("solver already present in search module")
    a=gen.find(START); b=gen.find(END,a)
    if a<0 or b<0: raise SystemExit("solver boundaries not found in generator")
    block=gen[a:b]
    if "return SearchOutcome(" not in block or "DepthNodeBudgetExhausted" not in block:
        raise SystemExit("solver block incomplete")
    # The extracted solver deliberately keeps the generator's geometry imports
    # available through the same module namespace; preserve them while moving
    # only the function itself.
    imports = """
from planet_finder_geometry import (
    SIGNS, W, H, RO, RI,
    label_size, reserved_boxes, xy, legal_candidate_positions,
    boxes_overlap, segment_hits_box, route, leader_hits_zodiac_rim,
    leaders_too_close,
)
from planet_finder_validation import validate_layout
"""
    MOD.write_text(mod.rstrip() + "\n" + imports + "\n" + block + "\n", encoding="utf-8")
    GEN.write_text(gen[:a]+gen[b+1:],encoding="utf-8")
    print(f"migrated {block.count(chr(10))+1} DFS lines")
if __name__=="__main__": main()
