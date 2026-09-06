#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W41 = ROOT / "observer-views" / "W41"
AQUARIUS = W41 / "sadalmelik-finder.svg"
ENIF = W41 / "enif-finder.svg"


def read(path: Path) -> str:
    assert path.is_file(), f"missing golden reference: {path}"
    text = path.read_text(encoding="utf-8")
    assert "<svg" in text, f"not an SVG: {path}"
    return text


def test_aquarius_golden_reference():
    text = read(AQUARIUS)
    assert "#ffd84d" in text, "Aquarius yellow target highlight missing"
    assert "Sadalmelik" in text, "Aquarius target label missing"
    assert "Water Jar" in text, "Aquarius Water Jar orientation/inset missing"
    assert "#59c86d" in text, "Aquarius asterism styling missing"
    assert "#5c8fe8" in text, "Aquarius constellation styling missing"
    assert "marker-end" not in text, "Aquarius arrow marker reappeared"


def test_enif_m15_golden_reference():
    text = read(ENIF)
    assert "Enif M15 Finder" in text, "approved Enif/M15 title changed"
    assert "#ffd84d" in text, "Enif/M15 yellow highlights missing"
    assert "M15" in text and "globular cluster" in text, "M15 label/type missing"
    assert "≈4°" in text, "Enif–M15 separation label missing"
    assert "#59c86d" in text, "Great Square styling missing"
    assert "#5c8fe8" in text, "Pegasus constellation styling missing"
    assert "marker-end" not in text, "Enif/M15 arrow marker reappeared"
