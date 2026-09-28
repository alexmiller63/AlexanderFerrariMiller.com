#!/usr/bin/env python3
"""Repair-once diagnostic: split the conjunction external leader gate."""
from pathlib import Path

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")

old = '''                if leader_hits_zodiac_rim(path_candidate) or leaders_too_close(\n                        path_candidate, leaders):\n                    report_widest_pair("leader_rim_or_external")\n                    diagnostic_rejections["leader_rim_or_external"] += 1\n                    conjunction_rejections_by_body[name]["leader_rim_or_external"] += 1\n                    chosen.pop(name, None)\n                    continue\n'''
new = '''                if leader_hits_zodiac_rim(path_candidate):\n                    report_widest_pair("leader_hits_zodiac_rim")\n                    diagnostic_rejections["leader_rim_or_external"] += 1\n                    conjunction_rejections_by_body[name]["leader_rim_or_external"] += 1\n                    chosen.pop(name, None)\n                    continue\n                if leaders_too_close(path_candidate, leaders):\n                    report_widest_pair("leaders_too_close_external")\n                    diagnostic_rejections["leader_rim_or_external"] += 1\n                    conjunction_rejections_by_body[name]["leader_rim_or_external"] += 1\n                    chosen.pop(name, None)\n                    continue\n'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"Refusing diagnostic: expected combined external leader gate exactly once, found {count}")
TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Split conjunction leader_rim_or_external diagnostic into rim and external-leader gates.")
