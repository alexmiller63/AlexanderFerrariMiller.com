#!/usr/bin/env python3
"""Safely move the fixed-order Planet Finder DFS into search support."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
GEN=ROOT/"tools"/"generate_planet_finders.py"
MOD=ROOT/"tools"/"planet_finder_search.py"
START="def _solve_order("
END="\n\ndef new_search_budget():"
IMPORT="from planet_finder_search import DepthNodeBudgetExhausted, SearchOutcome\n"
PRELUDE='''"""Planet Finder fixed-order DFS search implementation."""
from __future__ import annotations

import time

from planet_finder_geometry import (
    CANONICAL, SIGNS, FinderMode, Box, Body,
    label_size, reserved_boxes, xy, legal_candidate_positions,
    boxes_overlap, segment_hits_box, route, leader_hits_zodiac_rim,
    leaders_too_close,
)
from planet_finder_validation import validate_layout

'''
def main():
    t=GEN.read_text(encoding="utf-8")
    if "def _solve_order(" in MOD.read_text(encoding="utf-8"):
        if "from planet_finder_search import DepthNodeBudgetExhausted, SearchOutcome" not in t:
            raise SystemExit("search module has solver but generator import is absent")
        print("search extraction already applied"); return
    a=t.find(START); b=t.find(END,a)
    if a<0 or b<0: raise SystemExit("search boundaries not found")
    block=t[a:b]
    required=["def _solve_order(","DepthNodeBudgetExhausted","SearchOutcome","validate_layout(","legal_candidate_positions(","forward_check("]
    missing=[x for x in required if x not in block]
    if missing: raise SystemExit(f"incomplete search block: {missing}")
    MOD.write_text(MOD.read_text(encoding="utf-8")+PRELUDE+block+"\n",encoding="utf-8")
    nt=t[:a]+t[b+2:]
    GEN.write_text(nt,encoding="utf-8")
    print(f"extracted {block.count(chr(10))+1} DFS search lines")
if __name__=="__main__": main()
