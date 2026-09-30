#!/usr/bin/env python3
"""One-shot repair: make the W01/W02 diagnostic ladders faster and finer.

Production Planet Finder code and exact W01/W02 endpoints are untouched.
This changes only the progressive test ladder: 15-second rung budgets and
extra synthetic rungs immediately around the currently observed cliffs.
"""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tests/test_planet_finder_system.py")
text = TARGET.read_text(encoding="utf-8")

marker = "REGRESSION_SECONDS = 60.0\n"
if text.count(marker) != 1:
    raise SystemExit(f"Safety stop: regression clock marker count={text.count(marker)}; expected 1")
text = text.replace(marker, marker + "LADDER_SECONDS = 15.0\n", 1)

w01_old = '''    ("wrap-four", {"Sun": 180, "Mercury": 185, "Venus": 190, "Mars": 195, "Pluto": 200, "Saturn": 355.99936587038286, "Neptune": 359.4721293482971, "Ceres": 6.453439627692317, "Moon": 22.937571430229294, "Uranus": 80, "Jupiter": 120}),
    ("both-real-alignments", {"Mercury": 264.1023447351197, "Venus": 275.4313050776394, "Sun": 277.511945972904, "Mars": 280.39213202805865, "Pluto": 302.62909367404063, "Saturn": 355.99936587038286, "Neptune": 359.4721293482971, "Ceres": 6.453439627692317, "Moon": 22.937571430229294, "Uranus": 80, "Jupiter": 120}),'''
w01_new = '''    ("wrap-four", {"Sun": 180, "Mercury": 185, "Venus": 190, "Mars": 195, "Pluto": 200, "Saturn": 355.99936587038286, "Neptune": 359.4721293482971, "Ceres": 6.453439627692317, "Moon": 22.937571430229294, "Uranus": 80, "Jupiter": 120}),
    ("real-five-plus-wide-wrap", {"Mercury": 264.1023447351197, "Venus": 275.4313050776394, "Sun": 277.511945972904, "Mars": 280.39213202805865, "Pluto": 302.62909367404063, "Saturn": 345, "Neptune": 355, "Ceres": 5, "Moon": 15, "Uranus": 80, "Jupiter": 120}),
    ("real-five-plus-medium-wrap", {"Mercury": 264.1023447351197, "Venus": 275.4313050776394, "Sun": 277.511945972904, "Mars": 280.39213202805865, "Pluto": 302.62909367404063, "Saturn": 350, "Neptune": 358, "Ceres": 6, "Moon": 18, "Uranus": 80, "Jupiter": 120}),
    ("both-real-alignments", {"Mercury": 264.1023447351197, "Venus": 275.4313050776394, "Sun": 277.511945972904, "Mars": 280.39213202805865, "Pluto": 302.62909367404063, "Saturn": 355.99936587038286, "Neptune": 359.4721293482971, "Ceres": 6.453439627692317, "Moon": 22.937571430229294, "Uranus": 80, "Jupiter": 120}),'''
if text.count(w01_old) != 1:
    raise SystemExit(f"Safety stop: W01 boundary match count={text.count(w01_old)}; expected 1")
text = text.replace(w01_old, w01_new, 1)

w02_old = '''    ("venus-sun-conjunction", {"Venus": 100.0, "Sun": 100.405, "Mercury": 20, "Mars": 150, "Pluto": 190, "Saturn": 230, "Neptune": 270, "Ceres": 310, "Moon": 350, "Uranus": 50, "Jupiter": 200}),
    ("inner-alignment", {"Mercury": 274.8007325297467, "Venus": 284.23931723550777, "Sun": 284.6440014763892, "Mars": 285.7588826483691, "Pluto": 302.8404789942358, "Saturn": 20, "Neptune": 60, "Ceres": 100, "Moon": 140, "Uranus": 180, "Jupiter": 220}),'''
w02_new = '''    ("venus-sun-conjunction", {"Venus": 100.0, "Sun": 100.405, "Mercury": 20, "Mars": 150, "Pluto": 190, "Saturn": 230, "Neptune": 270, "Ceres": 310, "Moon": 350, "Uranus": 50, "Jupiter": 200}),
    ("inner-wide", {"Mercury": 270, "Venus": 282, "Sun": 284.6440014763892, "Mars": 290, "Pluto": 306, "Saturn": 20, "Neptune": 60, "Ceres": 100, "Moon": 140, "Uranus": 180, "Jupiter": 220}),
    ("inner-medium", {"Mercury": 272.5, "Venus": 283, "Sun": 284.6440014763892, "Mars": 288, "Pluto": 304.5, "Saturn": 20, "Neptune": 60, "Ceres": 100, "Moon": 140, "Uranus": 180, "Jupiter": 220}),
    ("inner-near", {"Mercury": 274, "Venus": 283.8, "Sun": 284.6440014763892, "Mars": 286.5, "Pluto": 303.5, "Saturn": 20, "Neptune": 60, "Ceres": 100, "Moon": 140, "Uranus": 180, "Jupiter": 220}),
    ("inner-alignment", {"Mercury": 274.8007325297467, "Venus": 284.23931723550777, "Sun": 284.6440014763892, "Mars": 285.7588826483691, "Pluto": 302.8404789942358, "Saturn": 20, "Neptune": 60, "Ceres": 100, "Moon": 140, "Uranus": 180, "Jupiter": 220}),'''
if text.count(w02_old) != 1:
    raise SystemExit(f"Safety stop: W02 boundary match count={text.count(w02_old)}; expected 1")
text = text.replace(w02_old, w02_new, 1)

# W01 budget is on one line; W02 is formatted across lines.
w01_budget = 'budget={"max_node_candidates": 2000, "max_seconds": REGRESSION_SECONDS}, context_label=f"ultimate-W01-'
if text.count(w01_budget) != 1:
    raise SystemExit(f"Safety stop: W01 budget match count={text.count(w01_budget)}; expected 1")
text = text.replace(w01_budget, 'budget={"max_node_candidates": 2000, "max_seconds": LADDER_SECONDS}, context_label=f"ultimate-W01-', 1)

w02_budget = 'budget={"max_node_candidates": 2000, "max_seconds": REGRESSION_SECONDS},'
w02_anchor = 'context_label=f"ultimate-W02-'
pos = text.find(w02_anchor)
if pos < 0:
    raise SystemExit("Safety stop: W02 context anchor missing")
before = text[:pos]
budget_pos = before.rfind(w02_budget)
if budget_pos < 0 or pos - budget_pos > 300:
    raise SystemExit("Safety stop: W02 nearby budget not found")
text = text[:budget_pos] + text[budget_pos:].replace(w02_budget, 'budget={"max_node_candidates": 2000, "max_seconds": LADDER_SECONDS},', 1)

TARGET.write_text(text, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print("Progressive W01/W02 ladders: 15-second rung budget plus finer W01/W02 boundary rungs. Exact endpoints and production solver unchanged. Repair Once is now OFF.")
