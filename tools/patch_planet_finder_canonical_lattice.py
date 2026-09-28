#!/usr/bin/env python3
"""Repair-once: permit the unavoidable initial leader crowding inside conjunctions.

Only the first segment versus first segment is exempted for conjunction siblings.
All later leader segments retain the normal crossing/grazing clearance, and
non-conjunction leaders retain the existing rule unchanged.  Completed-layout
validation receives the identical narrowly-scoped rule.
"""
from pathlib import Path

SEARCH = Path("tools/planet_finder_search_core.py")
VALIDATION = Path("tools/planet_finder_validation.py")
search = SEARCH.read_text(encoding="utf-8")
validation = VALIDATION.read_text(encoding="utf-8")


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Refusing repair: expected {label} exactly once, found {count}")
    return text.replace(old, new, 1)


# Inside solve_conjunction_group(), siblings are already known to be members of
# the same conjunction blob.  Their anchors can be nearly coincident, so the
# first segments need room to diverge.  Every other segment pair still gets the
# ordinary clearance test.
search = replace_once(
    search,
'''                if leaders_too_close(path_candidate, list(chosen_paths.values())):\n                    report_widest_pair("sibling_leaders_too_close")\n                    diagnostic_rejections["leader_rim_or_external"] += 1\n                    conjunction_rejections_by_body[name]["leader_rim_or_external"] += 1\n                    chosen.pop(name, None)\n                    continue\n''',
'''                sibling_leaders_too_close = any(\n                    segments_too_close(\n                        path_candidate[i], path_candidate[i + 1],\n                        old_path[j], old_path[j + 1],\n                        LEADER_TO_LEADER_CLEARANCE,\n                    )\n                    for old_path in chosen_paths.values()\n                    for i in range(len(path_candidate) - 1)\n                    for j in range(len(old_path) - 1)\n                    if not (i == 0 and j == 0)\n                )\n                if sibling_leaders_too_close:\n                    report_widest_pair("sibling_leaders_too_close_after_initial_escape")\n                    diagnostic_rejections["leader_rim_or_external"] += 1\n                    conjunction_rejections_by_body[name]["leader_rim_or_external"] += 1\n                    chosen.pop(name, None)\n                    continue\n''',
    "conjunction sibling leader gate",
)

# Independent final validation must enforce exactly the same exception or it
# would reject a conjunction layout that the solver correctly accepted.
validation = replace_once(
    validation,
'''    leader_hits_zodiac_rim, leaders_too_close,\n)\n''',
'''    leader_hits_zodiac_rim, leaders_too_close, segments_too_close,\n    LEADER_TO_LEADER_CLEARANCE, NEAR_CONJUNCTION_DEGREES,\n)\n''',
    "validation geometry import",
)
validation = replace_once(
    validation,
'''    # Leaders are mutually exclusive geometry.  This is intentionally a\n    # second, independent check after proposal-time rejection so a stale or\n    # future search-state bug can never render crossing/grazing leaders.\n    for i, path in enumerate(paths):\n        for j in range(i):\n            if leaders_too_close(path, [paths[j]]):\n                errors.append(\n                    f"{result[i][1]}: leader crosses or grazes {result[j][1]} leader"\n                )\n''',
'''    # Leaders are mutually exclusive geometry.  Conjunction siblings alone\n    # may crowd during their first segments while escaping nearly coincident\n    # body anchors; every later segment pair retains normal clearance.\n    def angular_distance(a, b):\n        return abs((a - b + 180.0) % 360.0 - 180.0)\n\n    for i, path in enumerate(paths):\n        for j in range(i):\n            conjunction_siblings = angular_distance(result[i][2], result[j][2]) <= NEAR_CONJUNCTION_DEGREES\n            if conjunction_siblings:\n                too_close = any(\n                    segments_too_close(\n                        path[a], path[a + 1], paths[j][b], paths[j][b + 1],\n                        LEADER_TO_LEADER_CLEARANCE,\n                    )\n                    for a in range(len(path) - 1)\n                    for b in range(len(paths[j]) - 1)\n                    if not (a == 0 and b == 0)\n                )\n            else:\n                too_close = leaders_too_close(path, [paths[j]])\n            if too_close:\n                errors.append(\n                    f"{result[i][1]}: leader crosses or grazes {result[j][1]} leader"\n                )\n''',
    "terminal leader validation",
)

SEARCH.write_text(search, encoding="utf-8")
VALIDATION.write_text(validation, encoding="utf-8")
print("Applied conjunction initial-leader escape fix to search and final validation.")
