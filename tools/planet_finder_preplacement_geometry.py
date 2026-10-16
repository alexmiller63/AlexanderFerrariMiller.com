"""Geometry-backed candidate domains for global Planet Finder preplacement.

This conservative first stage reserves label envelopes for every body.
Leader routing and final validation remain the responsibility of the existing
Planet Finder engine; box-only solutions are NOT finished chart layouts.
"""
from __future__ import annotations

from dataclasses import dataclass

from planet_finder_geometry import (
    Box, FinderMode, LABEL_COLLISION_PADDING, boxes_overlap,
    label_size, legal_candidate_positions, reserved_boxes,
    leaders_too_close, segment_hits_box, PLACED_LABEL_LEADER_CLEARANCE,
)
from planet_finder_preplacement import solve_preplacement


@dataclass(frozen=True)
class LabelCandidate:
    box: Box
    x: float
    y: float


def label_domains(mode, bodies, *, per_body_limit=120):
    """Return legal, widest-notation label domains for all chart bodies."""
    mode = FinderMode(mode)
    if per_body_limit < 1:
        raise ValueError("per_body_limit must be positive")
    # Each notation has distinct immutable text obstacles. Do not combine
    # reserved boxes across modes: doing so would reject legal solutions.
    reserved = reserved_boxes(mode)
    domains = {}
    for _, name, longitude in bodies:
        if name in domains:
            raise ValueError(f"duplicate body: {name}")
        sizes = [label_size(m, name) for m in FinderMode]
        width = max(w for w, _ in sizes)
        height = max(h for _, h in sizes)
        choices = []
        for x, y, box in legal_candidate_positions(longitude, width, height, reserved):
            choices.append(LabelCandidate(box, x, y))
            if len(choices) >= per_body_limit:
                break
        domains[name] = choices
    return domains


def preplace_labels(mode, bodies, *, per_body_limit=120, max_nodes=10000, deadline=None):
    """Plan label envelopes globally; caller MUST still route/validate leaders."""
    domains = label_domains(mode, bodies, per_body_limit=per_body_limit)
    return solve_preplacement(
        domains,
        lambda _a, x, _b, y: not boxes_overlap(
            x.box, y.box, LABEL_COLLISION_PADDING
        ),
        max_nodes=max_nodes,
        deadline=deadline,
    )


@dataclass(frozen=True)
class RoutedCandidate:
    """A candidate with a leader route already accepted by the route engine."""
    box: Box
    path: tuple[tuple[float, float], ...]


def routed_candidates_compatible(left: RoutedCandidate, right: RoutedCandidate) -> bool:
    """Check pairwise label and leader conflicts using existing geometry."""
    if boxes_overlap(left.box, right.box, LABEL_COLLISION_PADDING):
        return False
    if leaders_too_close(left.path, [right.path]):
        return False
    # The first segment may escape its own label/anchor, but may not cut
    # through another body's label at any point.
    for path, obstacle in ((left.path, right.box), (right.path, left.box)):
        if any(
            segment_hits_box(a, b, obstacle, PLACED_LABEL_LEADER_CLEARANCE)
            for a, b in zip(path, path[1:])
        ):
            return False
    return True


def preplace_routed_candidates(domains, *, max_nodes=10000, deadline=None):
    """Solve all-body routed domains with existing pairwise hard geometry.

    Caller must construct candidates using route() with immutable obstacles,
    then run validate_layout() on the completed assignment. This function
    does not substitute for the final validator.
    """
    return solve_preplacement(
        domains,
        lambda _a, x, _b, y: routed_candidates_compatible(x, y),
        max_nodes=max_nodes,
        deadline=deadline,
    )
