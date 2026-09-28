#!/usr/bin/env python3
"""Repair-once: allow conjunction sibling leaders to diverge from their crowded origins.

Ordinary leader clearance remains unchanged everywhere else.  Inside a conjunction
blob only, sibling leaders use the existing rim-escape-aware clearance helper,
which permits the unavoidable shared initial escape segment while retaining normal
clearance for all later segments.
"""
from pathlib import Path

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Refusing repair: expected {label} exactly once, found {count}")
    text = text.replace(old, new, 1)


# Import the already-established shared-anchor escape rule.  This helper skips
# only the first-vs-first segment when the two leaders share the same origin;
# every later segment pair still receives ordinary leader clearance.
replace_once(
'''from planet_finder_rim_anchors import (\n    anchor_candidates,\n''',
'''from planet_finder_rim_anchors import (\n    anchor_candidates,\n    leaders_too_close_after_rim_escape,\n''',
"rim-anchor import",
)

# Surgical conjunction-only correction.  Do not weaken the ordinary global
# leader rule used against leaders outside the conjunction blob.
replace_once(
'''                if leaders_too_close(path_candidate, list(chosen_paths.values())):\n                    report_widest_pair("sibling_leaders_too_close")\n                    diagnostic_rejections["leader_rim_or_external"] += 1\n                    diagnostic_rejections_by_body[name]["leader_rim_or_external"] += 1\n                    continue\n''',
'''                if leaders_too_close_after_rim_escape(path_candidate, list(chosen_paths.values())):\n                    report_widest_pair("sibling_leaders_too_close_after_escape")\n                    diagnostic_rejections["leader_rim_or_external"] += 1\n                    diagnostic_rejections_by_body[name]["leader_rim_or_external"] += 1\n                    continue\n''',
"conjunction sibling leader gate",
)

TARGET.write_text(text, encoding="utf-8")
print("Applied conjunction sibling leader escape fix; ordinary leader clearance unchanged.")
