#!/usr/bin/env python3
"""One-shot forensic instrumentation for Ceres forward-check blockers.

Diagnostic only: records blocker identities for every major rejection class
seen in the W36 Mixed JSM 25% forward viability gate. Solver legality,
candidate ordering, and budgets are unchanged. Self-disables after running.
"""
from pathlib import Path

ENABLED = True
if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

CORE = Path("tools/planet_finder_search_core.py")
core = CORE.read_text(encoding="utf-8")

anchor = '    forward_stats = {"checks": 0, "pruned": 0, "witnesses": 0, "by_body": {}}\n'
addition = anchor + '''    # Diagnostic only: blocker identities inside Ceres forward viability.
    forward_ceres_blockers = {
        "overlap": {}, "existing-leader": {}, "leader-graze": {},
        "route-direct": {}, "route-escape": {}, "route-arc": {}, "route-final": {},
    }
    forward_ceres_route_other = {}
'''
if core.count(anchor) != 1:
    raise SystemExit(f"Safety stop: forward_stats anchor count={core.count(anchor)}")
core = core.replace(anchor, addition, 1)

old = '''                if any(boxes_overlap(future_box, other, 14) for other in boxes):
                    reasons["placed-overlap"] += 1
                    continue
'''
new = '''                overlap_hits = [i for i, other in enumerate(boxes) if boxes_overlap(future_box, other, 14)]
                if overlap_hits:
                    reasons["placed-overlap"] += 1
                    if future_name == "Ceres":
                        for i in overlap_hits:
                            blocker = leader_names[i] if i < len(leader_names) else f"placed_{i}"
                            counts = forward_ceres_blockers["overlap"]
                            counts[blocker] = counts.get(blocker, 0) + 1
                    continue
'''
if core.count(old) != 1:
    raise SystemExit(f"Safety stop: overlap anchor count={core.count(old)}")
core = core.replace(old, new, 1)

old = '''                if any(
                    segment_hits_box(seg[i], seg[i + 1], future_box, 10)
                    for seg in paths
                    for i in range(len(seg) - 1)
                ):
                    reasons["existing-leader"] += 1
                    continue
'''
new = '''                leader_hits = [
                    j for j, seg in enumerate(paths)
                    if any(segment_hits_box(seg[i], seg[i + 1], future_box, 10)
                           for i in range(len(seg) - 1))
                ]
                if leader_hits:
                    reasons["existing-leader"] += 1
                    if future_name == "Ceres":
                        for j in leader_hits:
                            blocker = leader_names[j] if j < len(leader_names) else f"leader_{j}"
                            counts = forward_ceres_blockers["existing-leader"]
                            counts[blocker] = counts.get(blocker, 0) + 1
                    continue
'''
if core.count(old) != 1:
    raise SystemExit(f"Safety stop: existing-leader anchor count={core.count(old)}")
core = core.replace(old, new, 1)

old = '''                path = route(
                    anchor,
                    center,
                    obstacles_now,
                    allow_initial_escape_count=immutable_count,
                    prefix_cache=prefix_cache,
                )
                if path is None:
                    reasons["route"] += 1
                    continue
'''
new = '''                forward_route_diag = {} if future_name == "Ceres" else None
                path = route(
                    anchor,
                    center,
                    obstacles_now,
                    forward_route_diag,
                    allow_initial_escape_count=immutable_count,
                    prefix_cache=prefix_cache,
                )
                if path is None:
                    reasons["route"] += 1
                    if future_name == "Ceres":
                        obstacle_names = reserved_names + list(leader_names)
                        for diag_key, bucket in (
                            ("direct_blocked_by", "route-direct"),
                            ("escape_blocked_by", "route-escape"),
                            ("arc_blocked_by", "route-arc"),
                            ("final_blocked_by", "route-final"),
                        ):
                            for obstacle_index, count in forward_route_diag.get(diag_key, {}).items():
                                blocker = obstacle_names[obstacle_index] if obstacle_index < len(obstacle_names) else f"obstacle_{obstacle_index}"
                                counts = forward_ceres_blockers[bucket]
                                counts[blocker] = counts.get(blocker, 0) + count
                        for diag_key in ("anchor_blocked", "target_approach"):
                            count = forward_route_diag.get(diag_key, 0)
                            if count:
                                forward_ceres_route_other[diag_key] = forward_ceres_route_other.get(diag_key, 0) + count
                    continue
'''
if core.count(old) != 1:
    raise SystemExit(f"Safety stop: route anchor count={core.count(old)}")
core = core.replace(old, new, 1)

old = '''                if leaders_too_close(path, paths):
                    reasons["leader-graze"] += 1
'''
new = '''                if leaders_too_close(path, paths):
                    reasons["leader-graze"] += 1
                    if future_name == "Ceres":
                        _, blocker_pair = minimum_leader_separation(path, paths)
                        if blocker_pair is not None:
                            j = blocker_pair[0]
                            blocker = leader_names[j] if j < len(leader_names) else f"leader_{j}"
                            counts = forward_ceres_blockers["leader-graze"]
                            counts[blocker] = counts.get(blocker, 0) + 1
'''
if core.count(old) != 1:
    raise SystemExit(f"Safety stop: leader-graze anchor count={core.count(old)}")
core = core.replace(old, new, 1)

anchor = '''    return SearchOutcome(
        "SOLVED" if len(solutions) >= target_solutions else "EXHAUSTED",
'''
diag = '''    if exhausted and forward_ceres_blockers:
        for kind, counts in forward_ceres_blockers.items():
            top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:12]
            diagnostic_print(
                f"Planet Finder {mode}: FORWARD CERES BLOCKERS kind={kind} "
                + (" ".join(f"{name}={count:,}" for name, count in top) if top else "none"),
                flush=True,
            )
        diagnostic_print(
            f"Planet Finder {mode}: FORWARD CERES ROUTE-OTHER "
            + (" ".join(f"{name}={count:,}" for name, count in sorted(forward_ceres_route_other.items()))
               if forward_ceres_route_other else "none"),
            flush=True,
        )

''' + anchor
if core.count(anchor) != 1:
    raise SystemExit(f"Safety stop: terminal anchor count={core.count(anchor)}")
core = core.replace(anchor, diag, 1)
CORE.write_text(core, encoding="utf-8")

GEOM = Path("tools/planet_finder_geometry.py")
geom = GEOM.read_text(encoding="utf-8")

old = '''    elif diagnostic is not None:
        diagnostic["direct_blocked"] = diagnostic.get("direct_blocked", 0) + 1
'''
new = '''    elif diagnostic is not None:
        diagnostic["direct_blocked"] = diagnostic.get("direct_blocked", 0) + 1
        blocker = first_blocker(anchor, direct_endpoint if direct_endpoint is not None else center, skip_start_escape=True)
        if blocker is not None:
            by_obstacle = diagnostic.setdefault("direct_blocked_by", {})
            by_obstacle[blocker] = by_obstacle.get(blocker, 0) + 1
'''
if geom.count(old) != 1:
    raise SystemExit(f"Safety stop: direct-route anchor count={geom.count(old)}")
geom = geom.replace(old, new, 1)

old = '''            if not segment_clear(elbow1, elbow2):
                if diagnostic is not None:
                    diagnostic["arc_blocked"] = diagnostic.get("arc_blocked", 0) + 1
                continue
'''
new = '''            if not segment_clear(elbow1, elbow2):
                if diagnostic is not None:
                    diagnostic["arc_blocked"] = diagnostic.get("arc_blocked", 0) + 1
                    blocker = first_blocker(elbow1, elbow2)
                    if blocker is not None:
                        by_obstacle = diagnostic.setdefault("arc_blocked_by", {})
                        by_obstacle[blocker] = by_obstacle.get(blocker, 0) + 1
                continue
'''
if geom.count(old) != 1:
    raise SystemExit(f"Safety stop: arc-route anchor count={geom.count(old)}")
geom = geom.replace(old, new, 1)

old = '''            if final_endpoint is None or not segment_clear(elbow2, final_endpoint):
                if diagnostic is not None:
                    diagnostic["final_blocked"] = diagnostic.get("final_blocked", 0) + 1
                continue
'''
new = '''            if final_endpoint is None or not segment_clear(elbow2, final_endpoint):
                if diagnostic is not None:
                    diagnostic["final_blocked"] = diagnostic.get("final_blocked", 0) + 1
                    if final_endpoint is not None:
                        blocker = first_blocker(elbow2, final_endpoint)
                        if blocker is not None:
                            by_obstacle = diagnostic.setdefault("final_blocked_by", {})
                            by_obstacle[blocker] = by_obstacle.get(blocker, 0) + 1
                continue
'''
if geom.count(old) != 1:
    raise SystemExit(f"Safety stop: final-route anchor count={geom.count(old)}")
geom = geom.replace(old, new, 1)
GEOM.write_text(geom, encoding="utf-8")

me = Path(__file__)
self_text = me.read_text(encoding="utf-8")
arming_line = "ENABLED" + " = True"
matching_lines = [i for i, line in enumerate(self_text.splitlines()) if line.strip() == arming_line]
if len(matching_lines) != 1:
    raise SystemExit(f"Safety stop: arming line count={len(matching_lines)}")
self_lines = self_text.splitlines()
self_lines[matching_lines[0]] = "ENABLED = False"
me.write_text("\n".join(self_lines) + "\n", encoding="utf-8")

print("Installed complete Ceres forward-blocker attribution (overlap, existing leader, route segments, leader graze). Solver behavior unchanged. Repair Once is now OFF.")
