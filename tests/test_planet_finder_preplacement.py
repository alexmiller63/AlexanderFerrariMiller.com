"""Focused regression tests for the global preplacement search kernel."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from planet_finder_preplacement import solve_preplacement


class GlobalPreplacementTests(unittest.TestCase):
    def test_all_bodies_are_assigned(self):
        domains = {name: [0, 1, 2] for name in ("Sun", "Moon", "Mars")}
        result = solve_preplacement(domains, lambda a, x, b, y: x != y)
        self.assertEqual(result.reason, "solved")
        self.assertEqual(set(result.assignment), set(domains))
        self.assertEqual(len(set(result.assignment.values())), 3)

    def test_forward_check_rejects_dead_choice(self):
        domains = {"A": [0, 1], "B": [0], "C": [0, 1]}
        result = solve_preplacement(domains, lambda a, x, b, y: (a, x, b, y) not in {
            ("B", 0, "A", 0), ("A", 0, "B", 0),
        })
        self.assertEqual(result.reason, "solved")
        self.assertEqual(result.assignment["A"], 1)
        self.assertGreater(result.pruned, 0)

    def test_empty_domain(self):
        result = solve_preplacement({"A": [], "B": [1]}, lambda *args: True)
        self.assertEqual(result.reason, "empty-initial-domain")

    def test_node_budget_not_misreported_as_impossible(self):
        result = solve_preplacement({"A": [0], "B": [0]}, lambda *args: True, max_nodes=1)
        self.assertEqual(result.reason, "budget-exhausted")

    def test_deterministic(self):
        domains = {"Z": [3, 2], "A": [1, 2]}
        runs = [solve_preplacement(domains, lambda *args: True).assignment for _ in range(3)]
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[1], runs[2])


    def test_geometry_adapter_label_conflict(self):
        from planet_finder_geometry import Box
        from planet_finder_preplacement_geometry import (
            RoutedCandidate, routed_candidates_compatible,
        )
        left = RoutedCandidate(Box(100, 100, 40, 30), ((0, 0), (100, 100)))
        overlap = RoutedCandidate(Box(110, 100, 40, 30), ((0, 200), (110, 100)))
        self.assertFalse(routed_candidates_compatible(left, overlap))

    def test_geometry_adapter_separated_routes(self):
        from planet_finder_geometry import Box
        from planet_finder_preplacement_geometry import (
            RoutedCandidate, routed_candidates_compatible,
        )
        left = RoutedCandidate(Box(100, 100, 30, 30), ((100, 50), (100, 100)))
        right = RoutedCandidate(Box(300, 300, 30, 30), ((300, 250), (300, 300)))
        self.assertTrue(routed_candidates_compatible(left, right))

    def test_global_routed_assignment(self):
        from planet_finder_geometry import Box
        from planet_finder_preplacement_geometry import (
            RoutedCandidate, preplace_routed_candidates,
        )
        domains = {
            "Sun": [RoutedCandidate(Box(100, 100, 30, 30), ((100, 50), (100, 100)))],
            "Moon": [RoutedCandidate(Box(300, 300, 30, 30), ((300, 250), (300, 300)))],
        }
        result = preplace_routed_candidates(domains)
        self.assertEqual(result.reason, "solved")
        self.assertEqual(set(result.assignment), set(domains))


if __name__ == "__main__":
    unittest.main()
