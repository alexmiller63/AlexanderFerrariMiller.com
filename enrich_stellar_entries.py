#!/usr/bin/env python3
"""Enrich catalog-backed calendar entries with observer-facing metadata.

Identity and source magnitudes remain authoritative source data. Reader-facing
presentation is delegated to the shared Star Almanack object renderer so stars,
Messier objects, and future object classes use one presentation path.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
TOOLS = REPO_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from star_almanack_objects import AlmanackObject, observing_aid_for_magnitude, render_text

ROOT = Path(__file__).parent
TARGET = ROOT / "almanack-expanded.md"
BAYER = ROOT / "expanded-bayer-visibility-2026.csv"
BRIGHT = ROOT / "bright-star-visibility-2026.csv"
MESSIER = ROOT / "messier-visibility-2026.csv"
FIXED_OBJECTS = ROOT / "fixed-objects.yaml"

GREEK = {
    "Alp": "α", "Bet": "β", "Gam": "γ", "Del": "δ", "Eps": "ε",
    "Zet": "ζ", "Eta": "η", "The": "θ", "Iot": "ι", "Kap": "κ",
    "Lam": "λ", "Mu": "μ", "Nu": "ν", "Xi": "ξ", "Omi": "ο",
    "Pi": "π", "Rho": "ρ", "Sig": "σ", "Tau": "τ", "Ups": "υ",
    "Phi": "φ", "Chi": "χ", "Psi": "ψ", "Ome": "ω",
}
