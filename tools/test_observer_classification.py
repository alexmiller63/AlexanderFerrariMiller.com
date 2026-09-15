#!/usr/bin/env python3
"""Regression checks for shared stellar-pattern observer classification."""
from observer_classification import median_v, observer_class_for_members, observer_class_from_median_v


def main() -> None:
    assert median_v([1.0, 2.0, 3.0]) == 2.0
    assert median_v([1.0, 2.0, 4.0, 8.0]) == 3.0
    assert observer_class_from_median_v(3.0) == "naked_eye"
    assert observer_class_from_median_v(3.01) == "binoculars"
    assert observer_class_from_median_v(6.0) == "binoculars"
    assert observer_class_from_median_v(6.01) == "telescope"
    assert observer_class_for_members([1.0, 2.0, 4.0, 8.0]) == (3.0, "naked_eye")
    print("PASS: median-magnitude observer classification")


if __name__ == "__main__":
    main()
