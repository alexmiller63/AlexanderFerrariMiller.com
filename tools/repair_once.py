from pathlib import Path

ENABLED = True

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

changes = [
(
"""        chosen = {}
        chosen_paths = {}
        ordered_names = [item[1][1] for item in group_items]
""",
"""        chosen = {}
        chosen_paths = {}
        ordered_names = [item[1][1] for item in group_items]
        diagnostic_rejections = {
            "label_overlap": 0,
            "lambda_order": 0,
            "route": 0,
            "leader_label": 0,
            "leader_rim_or_external": 0,
            "sibling_leader_label": 0,
        }
"""
),
(
"""                if any(boxes_overlap(box, other[2], LABEL_COLLISION_PADDING)
                       for other in chosen.values()):
                    continue
""",
"""                if any(boxes_overlap(box, other[2], LABEL_COLLISION_PADDING)
                       for other in chosen.values()):
                    diagnostic_rejections["label_overlap"] += 1
                    continue
"""
),
(
"""                if not preserves_lambda_order():
                    chosen.pop(name, None)
                    continue
""",
"""                if not preserves_lambda_order():
                    diagnostic_rejections["lambda_order"] += 1
                    chosen.pop(name, None)
                    continue
"""
),
(
"""                if path_candidate is None:
                    chosen.pop(name, None)
                    continue
""",
"""                if path_candidate is None:
                    diagnostic_rejections["route"] += 1
                    chosen.pop(name, None)
                    continue
"""
),
(
"""                if any(segment_hits_box(path_candidate[i], path_candidate[i + 1], other_box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for other_box in other_boxes for i in range(len(path_candidate) - 1)):
                    chosen.pop(name, None)
                    continue
""",
"""                if any(segment_hits_box(path_candidate[i], path_candidate[i + 1], other_box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for other_box in other_boxes for i in range(len(path_candidate) - 1)):
                    diagnostic_rejections["leader_label"] += 1
                    chosen.pop(name, None)
                    continue
"""
),
(
"""                if leader_hits_zodiac_rim(path_candidate) or leaders_too_close(
                        path_candidate, leaders):
                    chosen.pop(name, None)
                    continue
""",
"""                if leader_hits_zodiac_rim(path_candidate) or leaders_too_close(
                        path_candidate, leaders):
                    diagnostic_rejections["leader_rim_or_external"] += 1
                    chosen.pop(name, None)
                    continue
"""
),
(
"""                if any(segment_hits_box(old_path[i], old_path[i + 1], box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for old_path in chosen_paths.values() for i in range(len(old_path) - 1)):
                    chosen.pop(name, None)
                    continue
""",
"""                if any(segment_hits_box(old_path[i], old_path[i + 1], box,
                                        PLACED_LABEL_LEADER_CLEARANCE)
                       for old_path in chosen_paths.values() for i in range(len(old_path) - 1)):
                    diagnostic_rejections["sibling_leader_label"] += 1
                    chosen.pop(name, None)
                    continue
"""
),
(
"""        if not assign(0):
            return None
""",
"""        if not assign(0):
            diagnostic_print(
                f"Planet Finder {mode}: conjunction diagnostics group {group_index + 1} "
                f"{' > '.join(item[1] for item in group)} "
                f"rejections={diagnostic_rejections}",
                flush=True,
            )
            return None
"""
),
]

for old, new in changes:
    if text.count(old) != 1:
        raise SystemExit(
            "Safety stop: expected exactly one occurrence of diagnostic target; "
            f"found {text.count(old)}"
        )
    text = text.replace(old, new, 1)

path.write_text(text)
print("Added conjunction rejection diagnostics; 0.25 refinement and all geometry rules unchanged.")
