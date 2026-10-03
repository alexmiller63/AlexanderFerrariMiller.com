"""Progressive W17 Greek ladder.

Build the exact 2026-W17 geometry one intentional interaction at a time.
Every rung asserts both its broad alignment groups and near-conjunction groups
before invoking the production layout solver.  That makes any accidental
alignment/conjunction a test-definition failure rather than a misleading
solver failure.
"""

from planet_finder_geometry import FinderMode, alignment_groups, conjunction_groups
from planet_finder_search import layout
from planet_finder_validation import validate_layout


W17 = {
    "Neptune": 2.894,
    "Mercury": 7.189,
    "Saturn": 7.870,
    "Mars": 7.905,
    "Sun": 29.933,
    "Ceres": 44.066,
    "Venus": 54.923,
    "Uranus": 59.677,
    "Moon": 64.792,
    "Jupiter": 107.510,
    "Pluto": 305.445,
}

ALIGNMENT_CHAIN = [
    "Neptune",
    "Mercury",
    "Saturn",
    "Mars",
    "Sun",
    "Ceres",
    "Venus",
    "Uranus",
    "Moon",
]

# The only W17 near-conjunction in this geometry is Saturn-Mars.
EXPECTED_CONJUNCTION = [["Saturn", "Mars"]]


def bodies_for(names):
    selected = set(names)
    parked = {"Neptune": 120.0, "Mercury": 145.0, "Saturn": 170.0, "Mars": 195.0, "Sun": 220.0, "Ceres": 245.0, "Venus": 270.0, "Uranus": 295.0, "Moon": 320.0, "Jupiter": 345.0, "Pluto": 95.0}
    return [(name.lower(), name, W17[name] if name in selected else parked[name]) for name in W17]


def names(groups):
    return [[item[1] for item in group] for group in groups]


def assert_valid(result, source):
    expected = {item[1] for item in source}
    actual = [item[1] for item in result]
    assert len(actual) == len(expected)
    assert set(actual) == expected
    valid, errors = validate_layout(FinderMode.GREEK, result)
    assert valid, errors


def expected_alignment(chain_count):
    return [ALIGNMENT_CHAIN[:chain_count]] if chain_count >= 2 else []


def expected_conjunction(chain_count):
    return EXPECTED_CONJUNCTION if chain_count >= 4 else []


# Build the difficult W17 alignment monotonically, then restore the two
# ordinary bodies.  No rung changes more than one intended ingredient.
W17_GREEK_LADDER = []
for count in range(2, len(ALIGNMENT_CHAIN) + 1):
    selected = ALIGNMENT_CHAIN[:count]
    W17_GREEK_LADDER.append(
        (
            f"alignment-{count}",
            selected,
            expected_alignment(count),
            expected_conjunction(count),
        )
    )

W17_GREEK_LADDER.extend(
    [
        (
            "alignment-9-plus-jupiter",
            ALIGNMENT_CHAIN + ["Jupiter"],
            [ALIGNMENT_CHAIN],
            EXPECTED_CONJUNCTION,
        ),
        (
            "exact-W17",
            ALIGNMENT_CHAIN + ["Jupiter", "Pluto"],
            [ALIGNMENT_CHAIN],
            EXPECTED_CONJUNCTION,
        ),
    ]
)


def test_w17_greek_progressive_ladder(monkeypatch):
    monkeypatch.setenv("PLANET_FINDER_DIAGNOSTIC_LEVEL", "2")
    passed = []

    for level, selected, expected_alignments, expected_conjunctions in W17_GREEK_LADDER:
        source = bodies_for(selected)

        actual_alignments = names(alignment_groups(source))
        actual_conjunctions = names(conjunction_groups(source))

        print(
            f"W17 LADDER {level} CLASSIFY "
            f"alignments={actual_alignments} conjunctions={actual_conjunctions}",
            flush=True,
        )

        # These assertions are deliberate guards against accidental geometry.
        assert actual_alignments == expected_alignments, (
            f"ACCIDENTAL/UNEXPECTED ALIGNMENT at {level}: "
            f"expected={expected_alignments} actual={actual_alignments}"
        )
        assert actual_conjunctions == expected_conjunctions, (
            f"ACCIDENTAL/UNEXPECTED CONJUNCTION at {level}: "
            f"expected={expected_conjunctions} actual={actual_conjunctions}"
        )

        print(f"W17 LADDER {level} START", flush=True)
        try:
            result = layout(
                FinderMode.GREEK,
                source,
                target_solutions=1,
                budget={"max_node_candidates": 200, "max_seconds": 30.0},
                context_label=f"W17-ladder-{level}",
            )
            assert_valid(result, source)
        except Exception as exc:
            print(
                f"W17 LADDER SUMMARY passed={passed} FIRST_FAILURE={level} "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            raise
        else:
            passed.append(level)
            print(f"W17 LADDER {level} PASS", flush=True)

    print(f"W17 LADDER SUMMARY ALL_PASS={passed}", flush=True)
