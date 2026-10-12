"""Deterministic, bounded global preplacement constraint solver.

This module is intentionally independent of rendering. Candidate objects can
carry existing label boxes and leader routes. The caller supplies a symmetric
compatibility predicate backed by Planet Finder's authoritative geometry.
No result is publishable without the existing final layout validator.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Mapping, Sequence, TypeVar
import time

T = TypeVar("T")


@dataclass(frozen=True)
class PreplacementResult(Generic[T]):
    assignment: dict[str, T] | None
    nodes: int
    pruned: int
    reason: str


def solve_preplacement(
    domains: Mapping[str, Sequence[T]],
    compatible: Callable[[str, T, str, T], bool],
    *,
    max_nodes: int = 10000,
    deadline: float | None = None,
) -> PreplacementResult[T]:
    """Find one complete assignment using MRV and forward checking.

    Candidate order is preserved for deterministic preference. This routine
    cannot establish impossibility when node/time limits are reached.
    """
    if max_nodes < 1:
        raise ValueError("max_nodes must be positive")
    names = tuple(sorted(domains))
    remaining = {name: tuple(domains[name]) for name in names}
    if any(not remaining[name] for name in names):
        return PreplacementResult(None, 0, 0, "empty-initial-domain")
    nodes = 0
    pruned = 0
    stopped = False

    def dfs(available: dict[str, tuple[T, ...]], chosen: dict[str, T]):
        nonlocal nodes, pruned, stopped
        if deadline is not None and time.monotonic() >= deadline:
            stopped = True
            return None
        if not available:
            return dict(chosen)
        # MRV, then deterministic name order. Candidate ranking remains
        # under the control of the existing geometry candidate generator.
        name = min(available, key=lambda n: (len(available[n]), n))
        rest = {n: values for n, values in available.items() if n != name}
        for candidate in available[name]:
            if nodes >= max_nodes:
                stopped = True
                return None
            if deadline is not None and time.monotonic() >= deadline:
                stopped = True
                return None
            nodes += 1
            reduced = {}
            viable = True
            for other, values in rest.items():
                keep = tuple(v for v in values if compatible(name, candidate, other, v))
                pruned += len(values) - len(keep)
                if not keep:
                    viable = False
                    break
                reduced[other] = keep
            if viable:
                chosen[name] = candidate
                answer = dfs(reduced, chosen)
                del chosen[name]
                if answer is not None:
                    return answer
                if stopped:
                    return None
        return None

    assignment = dfs(remaining, {})
    reason = "solved" if assignment is not None else ("budget-exhausted" if stopped else "no-compatible-assignment")
    return PreplacementResult(assignment, nodes, pruned, reason)
