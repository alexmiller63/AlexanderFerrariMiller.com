"""Planet Finder search support.

This module is being extracted incrementally from generate_planet_finders.py.
Keep changes behavior-preserving and validate each extraction before moving
additional search machinery here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchOutcome:
    """Result of one fixed-order DFS attempt."""

    kind: str
    solutions: list
    contest_keys: list
    blocker: str | None = None
    rejection_stats: dict | None = None


class DepthNodeBudgetExhausted(RuntimeError):
    """Signal that a body-depth node budget is exhausted for this DFS tree."""

    def __init__(self, depth: int, name: str):
        super().__init__(f"node budget exhausted at depth {depth} for {name}")
        self.depth = depth
        self.name = name
