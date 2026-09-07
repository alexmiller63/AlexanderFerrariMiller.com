#!/bin/sh
set -eu
python3 tools/clean_2025_2027_event_cells.py
python3 tools/populate_2025_2027_fixed_sky.py
