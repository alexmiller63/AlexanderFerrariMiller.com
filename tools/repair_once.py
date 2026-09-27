#!/usr/bin/env python3
"""One-shot diagnostic: expose which internal conjunction constraint is the barrier."""
from pathlib import Path

ENABLED = False
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

p = Path("tools/planet_finder_search_core.py")
s = p.read_text()

old = '''        diagnostic_rejections = {
            "label_overlap": 0,
            "lambda_order": 0,
            "route": 0,
            "leader_label": 0,
            "leader_rim_or_external": 0,
            "sibling_leader_label": 0,
        }
        conjunction_route_diagnostics = {}
'''
new = '''        diagnostic_rejections = {
            "label_overlap": 0,
            "lambda_order": 0,
            "route": 0,
            "leader_label": 0,
            "leader_rim_or_external": 0,
            "sibling_leader_label": 0,
        }
        # Diagnostic only: count rejections by conjunction depth/body so the
        # first hard barrier is visible without changing search semantics.
        conjunction_rejections_by_body = {
            name: {key: 0 for key in diagnostic_rejections}
            for name in ordered_names
        }
        conjunction_attempts_by_body = {name: 0 for name in ordered_names}
        conjunction_route_diagnostics = {}
'''
if s.count(old) != 1:
    raise SystemExit(f"Safety stop: expected rejection-dict marker once; found {s.count(old)}")
s = s.replace(old, new, 1)

old = '''            for row in pools[name]:
                x, y, box = row
                if any(boxes_overlap(box, other[2], LABEL_COLLISION_PADDING)
                       for other in chosen.values()):
                    diagnostic_rejections["label_overlap"] += 1
                    continue
'''
new = '''            for row in pools[name]:
                conjunction_attempts_by_body[name] += 1
                x, y, box = row
                if any(boxes_overlap(box, other[2], LABEL_COLLISION_PADDING)
                       for other in chosen.values()):
                    diagnostic_rejections["label_overlap"] += 1
                    conjunction_rejections_by_body[name]["label_overlap"] += 1
                    continue
'''
if s.count(old) != 1:
    raise SystemExit(f"Safety stop: expected candidate-loop marker once; found {s.count(old)}")
s = s.replace(old, new, 1)

replacements = [
('''                    diagnostic_rejections["lambda_order"] += 1
                    chosen.pop(name, None)
''', '''                    diagnostic_rejections["lambda_order"] += 1
                    conjunction_rejections_by_body[name]["lambda_order"] += 1
                    chosen.pop(name, None)
'''),
('''                    diagnostic_rejections["route"] += 1
                    chosen.pop(name, None)
''', '''                    diagnostic_rejections["route"] += 1
                    conjunction_rejections_by_body[name]["route"] += 1
                    chosen.pop(name, None)
'''),
('''                    diagnostic_rejections["leader_label"] += 1
                    chosen.pop(name, None)
''', '''                    diagnostic_rejections["leader_label"] += 1
                    conjunction_rejections_by_body[name]["leader_label"] += 1
                    chosen.pop(name, None)
'''),
('''                    diagnostic_rejections["leader_rim_or_external"] += 1
                    chosen.pop(name, None)
''', '''                    diagnostic_rejections["leader_rim_or_external"] += 1
                    conjunction_rejections_by_body[name]["leader_rim_or_external"] += 1
                    chosen.pop(name, None)
'''),
('''                    diagnostic_rejections["sibling_leader_label"] += 1
                    chosen.pop(name, None)
''', '''                    diagnostic_rejections["sibling_leader_label"] += 1
                    conjunction_rejections_by_body[name]["sibling_leader_label"] += 1
                    chosen.pop(name, None)
'''),
]
for old_piece, new_piece in replacements:
    if s.count(old_piece) != 1:
        raise SystemExit(f"Safety stop: expected rejection marker once; found {s.count(old_piece)} for {old_piece!r}")
    s = s.replace(old_piece, new_piece, 1)

old = '''                f"barrier={'internal' if blob_candidates == 0 else 'downstream'} "
                f"rejections={diagnostic_rejections} "
                f"route_detail={route_summary} "
'''
new = '''                f"barrier={'internal' if blob_candidates == 0 else 'downstream'} "
                f"attempts_by_body={conjunction_attempts_by_body} "
                f"rejections_by_body={conjunction_rejections_by_body} "
                f"rejections={diagnostic_rejections} "
                f"route_detail={route_summary} "
'''
if s.count(old) != 1:
    raise SystemExit(f"Safety stop: expected failure-summary marker once; found {s.count(old)}")
s = s.replace(old, new, 1)

p.write_text(s)
me = Path(__file__)
me.write_text(me.read_text().replace("ENABLED = True", "ENABLED = False", 1))
print("Installed per-body conjunction rejection diagnostics; Repair Once is now OFF.")
