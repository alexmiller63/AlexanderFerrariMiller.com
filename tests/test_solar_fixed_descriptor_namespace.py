#!/usr/bin/env python3
"""Regression guard: Solar System descriptor IDs cannot collide with fixed objects."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from sky_note_descriptors import SOLAR_SYSTEM_OBJECT_IDS, build_descriptors

# Build the minimal fixture without depending on an ephemeris or external data.
# A fixed star with the same numeric identity as Pluto must remain distinct.
records = build_descriptors(
    fixed=[{"type": "star", "name": "40 Eridani B", "fixed_object_id": 1260}],
    relations=[],
    stars=[],
    constellation_names={},
    asterisms={},
)
by_id = {str(record["id"]): record for record in records}
assert len(by_id) == len(records), "duplicate descriptor ID"
assert by_id["1260"]["name"] == "40 Eridani B"
assert by_id[f"solar-{SOLAR_SYSTEM_OBJECT_IDS['Pluto']}"]["name"] == "Pluto"
assert by_id["1260"]["type"] == "star"
print("PASS: Pluto and 40 Eridani B retain distinct descriptor identities")
