#!/usr/bin/env python3
"""Safely extract Planet Finder search controller and contest scoring."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
GEN=ROOT/"tools"/"generate_planet_finders.py"
MOD=ROOT/"tools"/"planet_finder_search.py"
START="def new_search_budget():\n"
END="\ndef generate_week(year: int, week: int):"
IMPORT_ANCHOR="from planet_finder_search import DepthNodeBudgetExhausted, SearchOutcome\n"
IMPORT="from planet_finder_search import DepthNodeBudgetExhausted, SearchOutcome, new_search_budget, layout\n"
PRELUDE='''\nimport math
import os
import time

from planet_finder_geometry import (
    CANONICAL, FinderMode, CX, CY, xy,
    DEFAULT_CANDIDATE_LAYOUTS, DEFAULT_MAX_NODE_CANDIDATES,
    DEFAULT_MAX_SEARCH_SECONDS,
)
\n'''
def main():
    t=GEN.read_text(encoding="utf-8")
    if "def new_search_budget(" in MOD.read_text(encoding="utf-8"):
        print("controller extraction already present"); return
    a=t.find(START); b=t.find(END,a)
    if a<0 or b<0: raise SystemExit("controller boundaries not found")
    block=t[a:b]
    for marker in ("def new_search_budget(","def layout(","def score(result):","contest_valid"):
        if marker not in block: raise SystemExit(f"controller marker missing: {marker}")
    # layout calls the fixed-order solver, which remains in the generator for now.
    block=block.replace(
        "            outcome = _solve_order(",
        "            from generate_planet_finders import _solve_order\n            outcome = _solve_order(",
        1,
    )
    MOD.write_text(MOD.read_text(encoding="utf-8")+PRELUDE+block+"\n",encoding="utf-8")
    nt=t[:a]+t[b+1:]
    nt=nt.replace(IMPORT_ANCHOR,IMPORT,1)
    GEN.write_text(nt,encoding="utf-8")
    print(f"extracted {block.count(chr(10))+1} controller/scoring lines")
if __name__=="__main__": main()
