#!/usr/bin/env python3
"""White Box entry point with diagnostic-only leader tracing enabled."""
from __future__ import annotations

import generate_planet_finders as _gpf
import white_box_planet_finder as _white_box
from white_box_leader_trace import traced_minimum_leader_separation

# white_box_planet_finder installs the normal diagnostic helper when imported.
# Replace only that diagnostic callback with the tracing wrapper.  Placement,
# routing, collision tests, clearances, and DFS behavior are unchanged.
_gpf.minimum_leader_separation = traced_minimum_leader_separation

if __name__ == "__main__":
    _white_box.main()
