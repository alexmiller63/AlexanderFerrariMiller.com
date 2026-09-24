#!/usr/bin/env python3
"""Safely remove the now-extracted Planet Finder DFS implementation."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
GEN=ROOT/"tools"/"generate_planet_finders.py"
START="def _solve_order("
END="\ndef generate_week(year: int, week: int):"
IMPORT="from planet_finder_search import DepthNodeBudgetExhausted, SearchOutcome, new_search_budget, layout\n"
def main():
    t=GEN.read_text(encoding="utf-8")
    if START not in t:
        print("DFS solver already removed"); return
    a=t.find(START); b=t.find(END,a)
    if a<0 or b<0: raise SystemExit("solver boundaries not found")
    block=t[a:b]
    if "def _solve_order(" not in block or "return SearchOutcome(" not in block:
        raise SystemExit("solver block incomplete")
    nt=t[:a]+t[b+1:]
    if IMPORT not in nt:
        raise SystemExit("search controller import missing")
    GEN.write_text(nt,encoding="utf-8")
    print(f"removed {block.count(chr(10))+1} extracted DFS lines")
if __name__=="__main__": main()
