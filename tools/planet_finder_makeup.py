"""Post-search cosmetic refinement for valid Planet Finder candidates.

The search solver establishes feasibility.  This module never participates in
DFS: it only tries local label/leader substitutions on already-valid complete
layouts, and accepts a substitution only when independent validation still
passes and the aesthetic cost improves.
"""
from __future__ import annotations

import math
import os
from collections import Counter

from planet_finder_geometry import (
    CX, CY, RI, Box, LABEL_LENGTH,
    label_size, legal_candidate_positions, reserved_boxes, route, xy,
)
from planet_finder_validation import validate_layout


def _diagnostic_level():
    try:
        return int(os.environ.get("PLANET_FINDER_DIAGNOSTIC_LEVEL", "0"))
    except ValueError:
        return 0


def _leader_length(path):
    return sum(
        math.hypot(b[0] - a[0], b[1] - a[1])
        for a, b in zip(path, path[1:])
    )


def _trace(level, message):
    if _diagnostic_level() >= level:
        print(f"[MAKEUP] {message}", flush=True)


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
                angle = math.degrees(math.acos(cosine))
                direction_cost += min(angle, 180.0 - angle)
        radial_cost += abs(math.hypot(box.x - CX, box.y - CY) - 345)
    return (elbows, direction_cost, length_cost, displacement_cost, radial_cost)


def _radial_deviation(path):
    """Angular deviation from the anchor's radial direction, in degrees."""
    if len(path) != 2:
        return math.inf
    ax, ay = path[0]
    bx, by = path[1]
    vx, vy = bx - ax, by - ay
    rx, ry = ax - CX, ay - CY
    vlen = math.hypot(vx, vy)
    rlen = math.hypot(rx, ry)
    if not vlen or not rlen:
        return math.inf
    cosine = max(-1.0, min(1.0, (vx * rx + vy * ry) / (vlen * rlen)))
    angle = math.degrees(math.acos(cosine))
    return min(angle, 180.0 - angle)


def _is_straight_radial(path, tolerance_degrees: float = 0.5):
    """True when a leader is a single, essentially radial segment."""
    return _radial_deviation(path) <= tolerance_degrees


def refine_candidate(mode, result, passes: int = 50):
    """Apply deterministic local makeup to one complete valid candidate."""
    current = list(result)
    ok, _ = validate_layout(mode, current)
    if not ok:
        return result

    _trace(1, f"START mode={mode} bodies={len(current)} score={aesthetic_score(current)}")
    for pass_index in range(max(1, passes)):
        changed = False
        _trace(2, f"PASS mode={mode} pass={pass_index + 1} score={aesthetic_score(current)}")
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
            old_length = _leader_length(old_path)
            old_deviation = _radial_deviation(old_path)
            legal_trials = []
            lattice_count = 0
            route_failures = 0
            validation_failures = Counter()

            _trace(
                2,
                f"BODY mode={mode} pass={pass_index + 1} name={name} "
                f"old_segments={max(0, len(old_path)-1)} old_length={old_length:.2f} "
                f"old_radial_dev={old_deviation:.3f} old_box=({old_box.x:.2f},{old_box.y:.2f})",
            )

            # The canonical legal lattice is finite and deterministic.  Makeup
            # may move a label, but it may not invent new geometry.
            for x, y, box in legal_candidate_positions(
                longitude, w, h, reserved_boxes(mode), displacement_scale=0.25
            ):
                lattice_count += 1
                path = route(
                    anchor, (x, y), obstacles,
                    allow_initial_escape_count=3,
                    target_box=box,
                    existing_paths=other_paths,
                )
                if path is None:
                    route_failures += 1
                    if _diagnostic_level() >= 3:
                        _trace(3, f"REJECT_ROUTE mode={mode} name={name} target=({x:.2f},{y:.2f})")
                    continue
                trial = list(current)
                trial[i] = (symbol, name, longitude, box, path)
                valid, reason = validate_layout(mode, trial)
                if valid:
                    score = aesthetic_score(trial)
                    legal_trials.append((trial, path, score))
                    if _diagnostic_level() >= 3:
                        _trace(
                            3,
                            f"VALID mode={mode} name={name} target=({x:.2f},{y:.2f}) "
                            f"segments={max(0, len(path)-1)} length={_leader_length(path):.2f} "
                            f"radial_dev={_radial_deviation(path):.3f} score={score}",
                        )
                else:
                    key = str(reason)
                    validation_failures[key] += 1
                    if _diagnostic_level() >= 3:
                        _trace(
                            3,
                            f"REJECT_VALIDATE mode={mode} name={name} target=({x:.2f},{y:.2f}) "
                            f"segments={max(0, len(path)-1)} length={_leader_length(path):.2f} "
                            f"radial_dev={_radial_deviation(path):.3f} reason={key}",
                        )

            radial_count = sum(_is_straight_radial(row[1]) for row in legal_trials)
            direct_count = sum(len(row[1]) == 2 for row in legal_trials)
            routed_count = len(legal_trials) - direct_count
            _trace(
                2,
                f"SUMMARY mode={mode} name={name} lattice={lattice_count} "
                f"route_fail={route_failures} validation_fail={sum(validation_failures.values())} "
                f"valid={len(legal_trials)} radial={radial_count} direct={direct_count} routed={routed_count}",
            )
            if validation_failures:
                _trace(2, f"VALIDATION_REASONS mode={mode} name={name} reasons={dict(validation_failures)}")
            direct_ranked = sorted(
                (row for row in legal_trials if len(row[1]) == 2),
                key=lambda row: (_radial_deviation(row[1]), row[2]),
            )
            for rank, (_, path, score) in enumerate(direct_ranked[:10], 1):
                _trace(
                    2,
                    f"DIRECT_RANK mode={mode} name={name} rank={rank} "
                    f"radial_dev={_radial_deviation(path):.3f} length={_leader_length(path):.2f} score={score}",
                )

            # Makeup invariant: if this body has any valid straight radial
            # leader, diagonal/elbowed alternatives are not eligible.  This is
            # deliberately stronger than a score bonus: straight wins whenever
            # geometry permits it.  Aesthetic scoring then chooses the nicest
            # member of that straight-only class.
            straight_trials = [row for row in legal_trials if _is_straight_radial(row[1])]
            if straight_trials:
                best, _, best_score = min(straight_trials, key=lambda row: row[2])
            else:
                # If exact radial is unavailable, prefer the least-diagonal
                # single-segment leader before considering its ordinary
                # aesthetic score.  This makes near-straight progressively
                # preferable to more diagonal straight leaders.
                direct_trials = [row for row in legal_trials if len(row[1]) == 2]
                if direct_trials:
                    best, _, best_score = min(
                        direct_trials,
                        key=lambda row: (_radial_deviation(row[1]), row[2]),
                    )
                else:
                    best = current
                    best_score = baseline
                    for trial, _, score in legal_trials:
                        if score < best_score:
                            best, best_score = trial, score

            if best is not current and best != current:
                new_path = best[i][4]
                _trace(
                    1,
                    f"ACCEPT mode={mode} pass={pass_index + 1} name={name} "
                    f"segments={max(0, len(old_path)-1)}->{max(0, len(new_path)-1)} "
                    f"length={old_length:.2f}->{_leader_length(new_path):.2f} "
                    f"radial_dev={old_deviation:.3f}->{_radial_deviation(new_path):.3f} "
                    f"score={baseline}->{best_score}",
                )
                current = best
                changed = True
            else:
                _trace(
                    2,
                    f"KEEP mode={mode} pass={pass_index + 1} name={name} "
                    f"legal={len(legal_trials)} score={baseline}",
                )
        if not changed:
            _trace(1, f"STABLE mode={mode} pass={pass_index + 1}")
            break
    _trace(1, f"END mode={mode} score={aesthetic_score(current)}")
    return current
