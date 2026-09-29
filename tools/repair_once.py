#!/usr/bin/env python3
"""One-shot diagnostic: trace the 1.08 -> 1.07 Venus-Sun alignment cliff."""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

TARGET = Path("tools/planet_finder_search_core.py")
text = TARGET.read_text(encoding="utf-8")
old = '''                if path is None or any(
                    segment_hits_box(path[i], path[i + 1], box, PLACED_LABEL_LEADER_CLEARANCE)
                    for box in other_boxes for i in range(len(path) - 1)
                ) or leader_hits_zodiac_rim(path) or leaders_too_close(
                    path, leaders + list(paths.values())
                ):
                    return None
                paths[name] = path
'''
new = '''                label_hit = path is not None and any(
                    segment_hits_box(path[i], path[i + 1], box, PLACED_LABEL_LEADER_CLEARANCE)
                    for box in other_boxes for i in range(len(path) - 1)
                )
                rim_hit = path is not None and leader_hits_zodiac_rim(path)
                prior_paths = leaders + list(paths.values())
                graze = path is not None and leaders_too_close(path, prior_paths)
                if path is None or label_hit or rim_hit or graze:
                    if os.environ.get("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF") == "1":
                        diagnostic_print(
                            f"Planet Finder {mode}: ALIGNMENT CLIFF TRACE body={name} "
                            f"route_none={path is None} label_hit={label_hit} rim_hit={rim_hit} "
                            f"leader_graze={graze} chosen={','.join(chosen.keys())}",
                            level=1, flush=True,
                        )
                    return None
                paths[name] = path
'''
if text.count(old) != 1:
    raise SystemExit("Safety stop: planned_paths legality block did not match exactly once")
TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")

TEST = Path("tests/test_planet_finder_w02_conjunction.py")
test = TEST.read_text(encoding="utf-8")
old_env = '    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "2")\n'
new_env = old_env + '    monkeypatch.setenv("PLANET_FINDER_TRACE_ALIGNMENT_CLIFF", "1")\n'
if test.count(old_env) != 1:
    raise SystemExit("Safety stop: diagnostic env marker did not match exactly once")
TEST.write_text(test.replace(old_env, new_env, 1), encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED = " + "True"
if self_text.count(arming_line) != 1:
    raise SystemExit("Safety stop: Repair Once arming marker is not unique")
me.write_text(self_text.replace(arming_line, "ENABLED = False", 1), encoding="utf-8")

print(
    "Added diagnostic-only alignment cliff tracing for route/label/rim/leader-graze predicates. "
    "No geometry, thresholds, candidate ordering, or acceptance behavior changed. Repair Once is now OFF."
)
