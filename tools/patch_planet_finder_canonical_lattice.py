#!/usr/bin/env python3
"""Repair-once diagnostic: identify the first validator rejecting the widest conjunction pair.

This patch changes no search decisions.  It records the first (widest-first)
candidate attempted for each conjunction depth and, for the second sibling,
reports the exact gate that rejects that widest pair.
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


replace_once(
'''        conjunction_attempts_by_body = {name: 0 for name in ordered_names}
        conjunction_route_diagnostics = {}
''',
'''        conjunction_attempts_by_body = {name: 0 for name in ordered_names}
        conjunction_route_diagnostics = {}
        # Forensic trace only: the conjunction pools are ordered widest-first.
        # Record exactly why the first widest sibling pair is rejected.
        widest_pair_trace = {"reported": False}
''',
"widest trace state",
)

replace_once(
'''            for row in candidate_rows:
                conjunction_attempts_by_body[name] += 1
                x, y, box = row
                if any(boxes_overlap(box, other[2], LABEL_COLLISION_PADDING)
                       for other in chosen.values()):
''',
'''            for row_index, row in enumerate(candidate_rows):
                conjunction_attempts_by_body[name] += 1
                x, y, box = row
                tracing_widest_pair = depth == 1 and row_index == 0 and not widest_pair_trace["reported"]

                def report_widest_pair(gate):
                    if not tracing_widest_pair or widest_pair_trace["reported"]:
                        return
                    first_name = ordered_names[0]
                    first_row = chosen.get(first_name)
                    separation = None
                    if first_row is not None:
                        separation = math.hypot(x - first_row[0], y - first_row[1])
                    print(
                        f"CONJUNCTION WIDEST PAIR mode={mode} group={group_index + 1} "
                        f"bodies={first_name} > {name} gate={gate} "
                        f"center_separation={separation if separation is not None else 'unknown'}",
                        flush=True,
                    )
                    widest_pair_trace["reported"] = True

                if any(boxes_overlap(box, other[2], LABEL_COLLISION_PADDING)
                       for other in chosen.values()):
                    report_widest_pair("label_overlap")
''',
"widest pair loop",
)

for old, new, label in [
    (
'''                if not lambda_ok:
                    diagnostic_rejections["lambda_order"] += 1
''',
'''                if not lambda_ok:
                    report_widest_pair("lambda_order")
                    diagnostic_rejections["lambda_order"] += 1
''',
"lambda gate",
    ),
    (
'''                if path_candidate is None:
                    diagnostic_rejections["route"] += 1
''',
'''                if path_candidate is None:
                    report_widest_pair("route")
                    diagnostic_rejections["route"] += 1
''',
"route gate",
    ),
    (
'''                if any(segment_hits_box(path_candidate[i], path_candidate[i + 1], other_box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for other_box in other_boxes for i in range(len(path_candidate) - 1)):
                    diagnostic_rejections["leader_label"] += 1
''',
'''                if any(segment_hits_box(path_candidate[i], path_candidate[i + 1], other_box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for other_box in other_boxes for i in range(len(path_candidate) - 1)):
                    report_widest_pair("leader_label")
                    diagnostic_rejections["leader_label"] += 1
''',
"leader-label gate",
    ),
    (
'''                if leader_hits_zodiac_rim(path_candidate) or leaders_too_close(
                        path_candidate, leaders):
                    diagnostic_rejections["leader_rim_or_external"] += 1
''',
'''                if leader_hits_zodiac_rim(path_candidate) or leaders_too_close(
                        path_candidate, leaders):
                    report_widest_pair("leader_rim_or_external")
                    diagnostic_rejections["leader_rim_or_external"] += 1
''',
"external leader gate",
    ),
    (
'''                if any(segment_hits_box(old_path[i], old_path[i + 1], box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for old_path in chosen_paths.values() for i in range(len(old_path) - 1)):
                    diagnostic_rejections["sibling_leader_label"] += 1
''',
'''                if any(segment_hits_box(old_path[i], old_path[i + 1], box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for old_path in chosen_paths.values() for i in range(len(old_path) - 1)):
                    report_widest_pair("sibling_leader_label")
                    diagnostic_rejections["sibling_leader_label"] += 1
''',
"sibling leader-label gate",
    ),
    (
'''                if leaders_too_close(path_candidate, list(chosen_paths.values())):
                    diagnostic_rejections["leader_rim_or_external"] += 1
''',
'''                if leaders_too_close(path_candidate, list(chosen_paths.values())):
                    report_widest_pair("sibling_leaders_too_close")
                    diagnostic_rejections["leader_rim_or_external"] += 1
''',
"sibling leader gate",
    ),
]:
    replace_once(old, new, label)

replace_once(
'''                chosen_paths[name] = path_candidate
                if assign(depth + 1):
''',
'''                report_widest_pair("accepted_internal_pair")
                chosen_paths[name] = path_candidate
                if assign(depth + 1):
''',
"accepted pair trace",
)

TARGET.write_text(text, encoding="utf-8")
print("Installed widest conjunction-pair validator diagnostic; search semantics unchanged.")
