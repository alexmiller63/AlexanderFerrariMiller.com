#!/usr/bin/env python3
"""Safely extract Planet Finder SVG rendering from the generator."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "tools" / "generate_planet_finders.py"
MOD = ROOT / "tools" / "planet_finder_rendering.py"
START = "def polyline(points):\n"
END = "\n\ndef parse_args():"
ANCHOR = "from planet_finder_validation import validate_layout\n"
IMPORT = "from planet_finder_rendering import polyline, render\n"
PRELUDE = '''"""Planet Finder SVG rendering."""\nfrom __future__ import annotations\n\nimport html\nfrom datetime import date\n\nfrom planet_finder_geometry import (\n    W, H, CX, CY, RO, RI, SIGNS, BODY_SYMBOLS, BODY_NAMES,\n    FinderMode, xy, label_size,\n)\n\n'''

def main():
    text = GEN.read_text(encoding="utf-8")
    if IMPORT in text:
        if not MOD.exists(): raise SystemExit("render import exists but module missing")
        print("render extraction already applied"); return
    if MOD.exists(): raise SystemExit("render module already exists")
    a = text.find(START); b = text.find(END, a)
    if a < 0 or b < 0: raise SystemExit("render boundaries not found")
    block = text[a:b]
    if "def render(" not in block or "</svg>" not in block:
        raise SystemExit("render block incomplete")
    # render calls layout; inject it to avoid a circular import at module import time.
    needle = "    placed = layout(mode, bodies, budget=budget, context_label=context_label)\n"
    if needle not in block:
        raise SystemExit("render layout call not found")
    block = block.replace(needle,
                          "    from generate_planet_finders import layout\n" + needle, 1)
    MOD.write_text(PRELUDE + block + "\n", encoding="utf-8")
    rewritten = text[:a] + text[b + 2:]
    if ANCHOR not in rewritten: raise SystemExit("import anchor missing")
    rewritten = rewritten.replace(ANCHOR, ANCHOR + IMPORT, 1)
    GEN.write_text(rewritten, encoding="utf-8")
    print(f"extracted {block.count(chr(10))+1} rendering lines")

if __name__ == "__main__": main()
