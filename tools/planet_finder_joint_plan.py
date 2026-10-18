"""Choose one complete label-and-leader plan usable in all notation modes.

Candidates include the existing longitude lattice and the chart interior.
Each candidate owns its route; constraint propagation rejects an earlier
choice as soon as it leaves another body without compatible access.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from functools import lru_cache
import math
import time

from planet_finder_geometry import (
    CX, CY, RI, Box, FinderMode,
    IMMUTABLE_LEADER_CLEARANCE, LABEL_COLLISION_PADDING,
    LABEL_RIM_CLEARANCE, PLACED_LABEL_LEADER_CLEARANCE,
    alignment_groups, boxes_overlap, leader_hits_zodiac_rim,
    leaders_too_close, legal_candidate_positions, reserved_boxes, route,
    segment_hits_box, universal_label_size, xy,
)
from planet_finder_validation import validate_layout
from planet_finder_makeup import uncross_labels

MODES = (FinderMode.GREEK, FinderMode.ENGLISH, FinderMode.MIXED)
# Successful plans only. Store immutable paths and return fresh copies so
# callers cannot mutate the plan shared by subsequent notation modes.
_PLAN_CACHE = OrderedDict()
_CACHE_LIMIT = 8


def _copy_plan(plan):
    return [(symbol, name, longitude, box, list(path))
            for symbol, name, longitude, box, path in plan]


def plan_universal_layout(bodies, deadline):
    """Return a first validated full plan, or None; honor the caller's clock.

    TimeoutError means this finite candidate set was not resolved in time,
    not that the sky geometry has no solution. Failed searches are not cached.
    """
    key = tuple(sorted(bodies, key=lambda item: (item[2] % 360.0, item[1])))
    cached = _PLAN_CACHE.get(key)
    if cached is not None:
        _PLAN_CACHE.move_to_end(key)
        by_name = {row[1]: row for row in _copy_plan(cached)}
        return [by_name[name] for _, name, _ in bodies]
    if time.monotonic() >= deadline:
        raise TimeoutError("joint placement deadline")

    reserved = []
    escape_indices = set()
    for mode in MODES:
        offset = len(reserved)
        reserved.extend(reserved_boxes(mode))
        escape_indices.update(range(offset, offset + 3))

    def check_deadline():
        if time.monotonic() >= deadline:
            raise TimeoutError("joint placement deadline")

    def clear_immutable(path):
        if leader_hits_zodiac_rim(path):
            return False
        anchor = path[0]
        padding = IMMUTABLE_LEADER_CLEARANCE
        for segment, (a, b) in enumerate(zip(path, path[1:])):
            for index, obstacle in enumerate(reserved):
                if segment == 0 and index in escape_indices and (
                    obstacle.left - padding <= anchor[0] <= obstacle.right + padding
                    and obstacle.top - padding <= anchor[1] <= obstacle.bottom + padding
                ):
                    continue
                if segment_hits_box(a, b, obstacle, padding):
                    return False
        return True

    interior = [xy(angle, radius)
                for radius in (360, 320, 280, 240, 200, 160, 120, 80)
                for angle in range(0, 360, 10)]
    pools = {}
    for index, (symbol, name, longitude) in enumerate(key):
        width, height = universal_label_size(name)
        anchor = xy(longitude, RI - 5)
        coordinates = interior + [
            (x, y) for x, y, _ in legal_candidate_positions(
                longitude, width, height, reserved, max_label_lengths=3.0)
        ]
        options = []
        for x, y in dict.fromkeys(coordinates):
            check_deadline()
            box = Box(x, y, width, height)
            if any(boxes_overlap(box, obstacle, LABEL_COLLISION_PADDING)
                   for obstacle in reserved):
                continue
            if any(math.hypot(px - CX, py - CY) >= RI - LABEL_RIM_CLEARANCE
                   for px in (box.left, box.right)
                   for py in (box.top, box.bottom)):
                continue
            path = route(anchor, (x, y), reserved,
                         allow_initial_escape_indices=escape_indices, target_box=box)
            if path is not None:
                options.append((symbol, name, longitude, box, path))

            # A bounded direct router's failure does not rule out this box.
            # Offer inward fan routes that turn earlier or later instead of
            # requiring every leader to follow the same direct approach.
            target_angle = (math.degrees(math.atan2(CY - y, x - CX)) - 180) % 360
            delta = (target_angle - longitude + 180) % 360 - 180
            target_radius = math.hypot(x - CX, y - CY)
            for exponent in (0.5, 2.0):
                middle = [xy(longitude + delta * t ** exponent,
                             (RI - 5) * (1 - t) + target_radius * t)
                          for t in (0.33, 0.66)]
                tail = route(middle[-1], (x, y), reserved, target_box=box)
                if tail is None:
                    continue
                alternative = [anchor, *middle[:-1], *tail]
                if alternative != path and clear_immutable(alternative):
                    options.append((symbol, name, longitude, box, alternative))
        # Keep all legal alternatives, preferring short routes with few bends.
        options.sort(key=lambda row: (
            len(row[4]), sum(math.dist(a, b) for a, b in zip(row[4], row[4][1:]))))
        if not options:
            return None
        pools[index] = options

    group_order = {}
    for group in alignment_groups(key):
        reference = group[0][2] - 90
        for position, (_, name, _) in enumerate(group):
            group_order[name] = (group[0][1], position, reference)
    angles = {
        id(row): ((math.degrees(math.atan2(CY - row[3].y, row[3].x - CX)) - 180)
                  % 360 - group_order[row[1]][2]) % 360
        for options in pools.values() for row in options if row[1] in group_order
    }

    def compatible(left, right):
        first = group_order.get(left[1])
        second = group_order.get(right[1])
        if first is not None and second is not None and first[0] == second[0]:
            a, b = angles[id(left)], angles[id(right)]
            if a == b or (a < b) != (first[1] < second[1]):
                return False
        if boxes_overlap(left[3], right[3], LABEL_COLLISION_PADDING):
            return False
        for source, target in ((left, right), (right, left)):
            if any(segment_hits_box(a, b, target[3], PLACED_LABEL_LEADER_CLEARANCE)
                   for a, b in zip(source[4], source[4][1:])):
                return False
        return not leaders_too_close(left[4], [right[4]])

    witness = {}

    @lru_cache(maxsize=500000)
    def pair(i, a, j, b):
        return compatible(pools[i][a], pools[j][b])

    def propagate(domains, changed=None):
        # Arc consistency: every surviving candidate must have at least one
        # compatible label-and-route candidate for every other body.
        queue = deque((i, j) for i in domains for j in domains
                      if i != j and (changed is None or j == changed))
        while queue:
            check_deadline()
            i, j = queue.popleft()
            supported = set()
            for a in domains[i]:
                previous = witness.get((i, a, j))
                if previous is not None and previous in domains[j]:
                    supported.add(a)
                    continue
                for b in domains[j]:
                    if pair(i, a, j, b):
                        witness[i, a, j] = b
                        supported.add(a)
                        break
            if len(supported) != len(domains[i]):
                if not supported:
                    return None
                domains[i] = supported
                queue.extend((k, i) for k in domains if k != i and k != j)
        return domains

    def solve(domains):
        check_deadline()
        if all(len(domain) == 1 for domain in domains.values()):
            return [pools[i][next(iter(domains[i]))] for i in range(len(key))]
        index = min((i for i in domains if len(domains[i]) > 1),
                    key=lambda i: len(domains[i]))
        for candidate in sorted(domains[index]):
            narrowed = dict(domains)
            narrowed[index] = {candidate}
            consistent = propagate(narrowed, changed=index)
            if consistent is not None:
                result = solve(consistent)
                if result is not None:
                    return result
        return None

    try:
        domains = propagate({i: set(range(len(options))) for i, options in pools.items()})
        result = solve(domains) if domains is not None else None
    finally:
        pair.cache_clear()
    if result is None:
        return None
    result = uncross_labels(MODES, result)
    for mode in MODES:
        valid, errors = validate_layout(mode, result)
        if not valid:
            raise AssertionError(f"Joint plan failed {mode.name} validation: {errors}")
    frozen = tuple((symbol, name, longitude, box, tuple(path))
                   for symbol, name, longitude, box, path in result)
    _PLAN_CACHE[key] = frozen
    if len(_PLAN_CACHE) > _CACHE_LIMIT:
        _PLAN_CACHE.popitem(last=False)
    by_name = {row[1]: row for row in _copy_plan(frozen)}
    return [by_name[name] for _, name, _ in bodies]
