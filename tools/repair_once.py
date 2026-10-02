#!/usr/bin/env python3
"""One-shot: make Planet Finder routing leader-aware and retry alternate routes."""

from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

GEOM = Path("tools/planet_finder_geometry.py")
CORE = Path("tools/planet_finder_search_core.py")

geom = GEOM.read_text(encoding="utf-8")
core = CORE.read_text(encoding="utf-8")

old_sig = """def route(anchor: tuple[float, float], center: tuple[float, float], obstacles: list[Box], diagnostic=None, allow_initial_escape_count: int = 0, prefix_cache: dict | None = None, allow_initial_escape_indices: set[int] | None = None, target_box: Box | None = None, allow_angular_escape: bool = False) -> list[tuple[float, float]] | None:
"""
new_sig = """def route(anchor: tuple[float, float], center: tuple[float, float], obstacles: list[Box], diagnostic=None, allow_initial_escape_count: int = 0, prefix_cache: dict | None = None, allow_initial_escape_indices: set[int] | None = None, target_box: Box | None = None, allow_angular_escape: bool = False, existing_paths: list[list[tuple[float, float]]] | None = None) -> list[tuple[float, float]] | None:
"""
if geom.count(old_sig) != 1:
    raise SystemExit(f"Safety stop: route signature count={geom.count(old_sig)}")
geom = geom.replace(old_sig, new_sig, 1)

old_target = """    def route_clear_of_target(path) -> bool:
        if target_box is None:
            return True
        if len(path) < 2:
            return False
        for i in range(len(path) - 2):
            if segment_hits_box(path[i], path[i + 1], target_box, IMMUTABLE_LEADER_CLEARANCE):
                return False
        return not segment_hits_box(path[-2], path[-1], target_box, -0.5)

"""
new_target = """    def route_clear_of_target(path) -> bool:
        if target_box is None:
            return True
        if len(path) < 2:
            return False
        for i in range(len(path) - 2):
            if segment_hits_box(path[i], path[i + 1], target_box, IMMUTABLE_LEADER_CLEARANCE):
                return False
        return not segment_hits_box(path[-2], path[-1], target_box, -0.5)

    # A route is not successful merely because it clears label obstacles.
    # Existing leader geometry is part of routing legality.  If a candidate
    # route crosses/grazes a leader, keep searching this SAME label position
    # for another route instead of throwing the label position away.
    def route_acceptable(path) -> bool:
        if not route_clear_of_target(path):
            return False
        if existing_paths and leaders_too_close(path, existing_paths):
            if diagnostic is not None:
                diagnostic["existing_leader_blocked"] = diagnostic.get(
                    "existing_leader_blocked", 0
                ) + 1
            return False
        return True

"""
if geom.count(old_target) != 1:
    raise SystemExit(f"Safety stop: target helper count={geom.count(old_target)}")
geom = geom.replace(old_target, new_target, 1)

old_direct = """        if route_clear_of_target(candidate):
            return candidate
"""
new_direct = """        if route_acceptable(candidate):
            return candidate
"""
if geom.count(old_direct) != 1:
    raise SystemExit(f"Safety stop: direct return count={geom.count(old_direct)}")
geom = geom.replace(old_direct, new_direct, 1)

old_offsets = """        offsets = (0.0,)
        if allow_angular_escape:
"""
new_offsets = """        offsets = (0.0,)
        if allow_angular_escape or existing_paths:
"""
if geom.count(old_offsets) != 1:
    raise SystemExit(f"Safety stop: offset gate count={geom.count(old_offsets)}")
geom = geom.replace(old_offsets, new_offsets, 1)

old_elbow = """            if route_clear_of_target(candidate):
                return candidate
"""
new_elbow = """            if route_acceptable(candidate):
                return candidate
"""
if geom.count(old_elbow) != 1:
    raise SystemExit(f"Safety stop: elbow return count={geom.count(old_elbow)}")
geom = geom.replace(old_elbow, new_elbow, 1)

# Ordinary DFS: existing leaders are part of route selection.
old = """                prefix_cache=route_prefix_cache,
                target_box=box,
            )
"""
new = """                prefix_cache=route_prefix_cache,
                target_box=box,
                existing_paths=leaders,
            )
"""
if core.count(old) != 1:
    raise SystemExit(f"Safety stop: ordinary route call count={core.count(old)}")
core = core.replace(old, new, 1)

# Forward checking must use the same leader-aware routing contract.
old = """                    prefix_cache=prefix_cache,
                    target_box=future_box,
                )
"""
new = """                    prefix_cache=prefix_cache,
                    target_box=future_box,
                    existing_paths=paths,
                )
"""
if core.count(old) != 1:
    raise SystemExit(f"Safety stop: forward route call count={core.count(old)}")
core = core.replace(old, new, 1)

# Alignment planning: retry alternate routes around both already-placed
# leaders and leaders selected earlier in the same planned blob.
old = """                path = route(
                    anchors[name], (x, y), reserved + placed + other_boxes,
                    allow_initial_escape_count=3,
                    target_box=chosen[name][2],
                )
                label_hit = path is not None and any(
"""
new = """                prior_paths = leaders + list(paths.values())
                path = route(
                    anchors[name], (x, y), reserved + placed + other_boxes,
                    allow_initial_escape_count=3,
                    target_box=chosen[name][2],
                    existing_paths=prior_paths,
                )
                label_hit = path is not None and any(
"""
if core.count(old) != 1:
    raise SystemExit(f"Safety stop: alignment route call count={core.count(old)}")
core = core.replace(old, new, 1)

# The old line remains useful as a defensive validation check, but do not
# reconstruct it after routing; it is already defined before route().
old = """                prior_paths = leaders + list(paths.values())
                graze = path is not None and leaders_too_close(path, prior_paths)
"""
new = """                graze = path is not None and leaders_too_close(path, prior_paths)
"""
if core.count(old) != 1:
    raise SystemExit(f"Safety stop: alignment prior_paths count={core.count(old)}")
core = core.replace(old, new, 1)

GEOM.write_text(geom, encoding="utf-8")
CORE.write_text(core, encoding="utf-8")

# Self-disable only after every guarded replacement succeeded.
me = Path(__file__)
source = me.read_text(encoding="utf-8")
needle = "\nENABLED = True\n"
if source.count(needle) != 1:
    raise SystemExit("Safety stop: ENABLED assignment not uniquely identifiable")
source = source.replace(needle, "\nENABLED = False\n", 1)
me.write_text(source, encoding="utf-8")

print(
    "Leader-aware routing installed: direct leader collisions now retry "
    "progressive left/right routes for the same label candidate; Repair Once is OFF."
)
