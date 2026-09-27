#!/usr/bin/env python3
"""One-shot repair: reject leader collisions within a conjunction blob."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

p = Path("tools/planet_finder_search_core.py")
s = p.read_text(encoding="utf-8")
old = '''                # Symmetric collision check: an already chosen sibling leader
                # may not pass through this newly chosen label.
                if any(segment_hits_box(old_path[i], old_path[i + 1], box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for old_path in chosen_paths.values() for i in range(len(old_path) - 1)):
                    diagnostic_rejections["sibling_leader_label"] += 1
                    conjunction_rejections_by_body[name]["sibling_leader_label"] += 1
                    chosen.pop(name, None)
                    continue
                chosen_paths[name] = path_candidate
'''
new = '''                # Symmetric collision check: an already chosen sibling leader
                # may not pass through this newly chosen label.
                if any(segment_hits_box(old_path[i], old_path[i + 1], box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for old_path in chosen_paths.values() for i in range(len(old_path) - 1)):
                    diagnostic_rejections["sibling_leader_label"] += 1
                    conjunction_rejections_by_body[name]["sibling_leader_label"] += 1
                    chosen.pop(name, None)
                    continue
                # A conjunction blob must satisfy the same leader-to-leader
                # clearance required by terminal validation.  Reject sibling
                # crossings/grazes here, before an impossible blob is handed
                # to the downstream DFS.
                if leaders_too_close(path_candidate, list(chosen_paths.values())):
                    diagnostic_rejections["leader_rim_or_external"] += 1
                    conjunction_rejections_by_body[name]["leader_rim_or_external"] += 1
                    chosen.pop(name, None)
                    continue
                chosen_paths[name] = path_candidate
'''
if s.count(old) != 1:
    raise SystemExit(f"Safety stop: expected sibling-leader insertion marker once; found {s.count(old)}")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

me = Path(__file__)
me.write_text(me.read_text(encoding="utf-8").replace("ENABLED = True", "ENABLED = False", 1), encoding="utf-8")
print("Installed conjunction sibling leader collision rejection; Repair Once is now OFF.")
