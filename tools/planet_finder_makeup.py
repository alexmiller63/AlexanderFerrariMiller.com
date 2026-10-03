"""Post-search cosmetic refinement for valid Planet Finder candidates.

The search solver establishes feasibility.  This module never participates in
DFS: it only tries local label/leader substitutions on already-valid complete
layouts, and accepts a substitution only when independent validation still
passes and the aesthetic cost improves.
"""
from __future__ import annotations

import math

from planet_finder_geometry import (
    CX, CY, RI, Box, LABEL_LENGTH,
    label_size, legal_candidate_positions, reserved_boxes, route, xy,
)
from planet_finder_validation import validate_layout


def aesthetic_score(result):
    """Prefer clean, attractively short leaders without crushing labels inward."""
    elbows = 0
    length_cost = 0.0
    displacement_cost = 0.0
    radial_cost = 0.0
    direction_cost = 0.0
    preferred_leader = 95.0
    for _, _, longitude, box, path in result:
        leader_length = sum(
            math.hypot(b[0] - a[0], b[1] - a[1])
            for a, b in zip(path, path[1:])
        )
        elbows += max(0, len(path) - 2)
        # A small leader is good, but zero is not the goal.  Penalize excess
        # length much more strongly than modest shortness around a readable
        # visual target.
        if leader_length > preferred_leader:
            length_cost += (leader_length - preferred_leader) ** 2
        else:
            length_cost += 0.18 * (preferred_leader - leader_length) ** 2
        natural = xy(longitude, 345)
        displacement_cost += math.hypot(box.x - natural[0], box.y - natural[1])
        # Prefer a leader that continues straight outward from its anchor.
        # A diagonal/slanting leader can still win when geometry requires it,
        # but not merely because it is a little shorter.
        if len(path) >= 2:
            ax, ay = path[0]
            bx, by = path[-1]
            vx, vy = bx - ax, by - ay
            rx, ry = ax - CX, ay - CY
            vlen = math.hypot(vx, vy)
            rlen = math.hypot(rx, ry)
            if vlen and rlen:
                cosine = max(-1.0, min(1.0, (vx * rx + vy * ry) / (vlen * rlen)))
                direction_cost += math.degrees(math.acos(cosine))
        radial_cost += abs(math.hypot(box.x - CX, box.y - CY) - 345)
    return (elbows, direction_cost, length_cost, displacement_cost, radial_cost)


def refine_candidate(mode, result, passes: int = 50):
    """Apply deterministic local makeup to one complete valid candidate."""
    current = list(result)
    ok, _ = validate_layout(mode, current)
    if not ok:
        return result

    for _ in range(max(1, passes)):
        changed = False
        # Work longest leaders first: they have the most visible makeup to gain.
        order = sorted(
            range(len(current)),
            key=lambda i: -sum(
                math.hypot(b[0] - a[0], b[1] - a[1])
                for a, b in zip(current[i][4], current[i][4][1:])
            ),
        )
        for i in order:
            symbol, name, longitude, old_box, old_path = current[i]
            w, h = label_size(mode, name)
            other_boxes = [row[3] for j, row in enumerate(current) if j != i]
            other_paths = [row[4] for j, row in enumerate(current) if j != i]
            obstacles = reserved_boxes(mode) + other_boxes
            anchor = xy(longitude, RI - 5)
            baseline = aesthetic_score(current)
            best = current
            best_score = baseline

            # The canonical legal lattice is finite and deterministic.  Makeup
            # may move a label, but it may not invent new geometry.
            for x, y, box in legal_candidate_positions(
                longitude, w, h, reserved_boxes(mode), displacement_scale=0.25
            ):
                path = route(
                    anchor, (x, y), obstacles,
                    allow_initial_escape_count=3,
                    target_box=box,
                    existing_paths=other_paths,
                )
                if path is None:
                    continue
                trial = list(current)
                trial[i] = (symbol, name, longitude, box, path)
                valid, _ = validate_layout(mode, trial)
                if not valid:
                    continue
                score = aesthetic_score(trial)
                if score < best_score:
                    best, best_score = trial, score

            if best is not current:
                current = best
                changed = True
        if not changed:
            break
    return current
