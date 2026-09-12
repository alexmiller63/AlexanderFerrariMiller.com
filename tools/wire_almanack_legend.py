#!/usr/bin/env python3
"""Ensure requested Almanack weekly pages have the same complete notation legend.

Canonical ephemeris-body legend order: Sun, Moon, Mercury, Venus, Mars, Ceres,
Jupiter, Saturn, Uranus, Neptune, Pluto.

The legend is the canonical reader-facing explanation of every symbol family used
by the Star Almanack, including observing-aid and event glyphs.

This file is also the deployment trigger for refreshing stale static legends.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BASES = (ROOT / "almanack", ROOT / "Star-Almanack-Repo" / "site")

STYLE = """<style id="almanack-legend-css">
.notation-legend {
  max-width:1080px;
  margin:0 auto;
  padding:1rem 1.5rem 1.35rem;
  font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:.88rem;
}
.notation-legend p { max-width:none; margin:.35rem 0; }
.legend-line { display:flex; flex-wrap:wrap; gap:.45rem 1rem; align-items:center; }
.legend-item { white-space:nowrap; }
.text-symbol { font-size:2em; line-height:.75; vertical-align:-.12em; font-variant-emoji:text; }
/* Canonical astronomical-symbol sizing. Zodiac, solar-system, and Bayer Greek
   symbols are all twice normal text size. Labels, constellation abbreviations,
   and coordinates remain at normal text size. */
.zodiac-glyph {
  display:inline-block;
  font-family:'Apple Symbols','Arial Unicode MS','Segoe UI Symbol','Noto Sans Symbols 2',serif;
  font-variant-emoji:text;
  color:currentColor;
  -webkit-text-fill-color:currentColor;
  font-size:2em;
  line-height:.75;
  vertical-align:-.12em;
}
.ephemeris-notation-item {
  display:inline-block;
}
.ephemeris-notation-item::first-letter,
.calendar-notation-item::first-letter,
.notation-item::first-letter {
  font-size:2em;
  line-height:.75;
}
.ephemeris-symbol {
  display:inline-block;
  font-family:'Apple Symbols','Arial Unicode MS','Segoe UI Symbol','Noto Sans Symbols 2',serif;
  font-variant-emoji:text;
  color:currentColor;
  -webkit-text-fill-color:currentColor;
  font-size:2em;
  line-height:.75;
  vertical-align:-.12em;
}
/* One canonical size for every observing/event glyph.  This deliberately
   overrides legacy inline sizes and also prevents intrinsically large SVGs in
   the Extended targets visibility row from rendering oversized. */
.visibility-glyph { height:2.3em !important; width:auto !important; vertical-align:-.55em !important; }
.legend-glyph { height:2.3em; width:auto; vertical-align:-.55em; margin-right:.2rem; }
.legend-explanation { white-space:normal; }
</style>"""

LEGEND = """<aside class="notation-legend" aria-label="Astronomical notation legend">
  <p><strong>Observing aid</strong> — these glyphs say how the target is intended to be observed; they do not identify the kind of astronomical object.</p>
  <div class="legend-line">
    <span class="legend-item"><img class="legend-glyph" src="/assets/almanack/visibility-glyphs/masters/eye.svg" alt="Naked-eye glyph"> Naked eye</span>
    <span class="legend-item"><img class="legend-glyph" src="/assets/almanack/visibility-glyphs/masters/binoculars.svg" alt="Binoculars glyph"> Binoculars</span>
    <span class="legend-item"><img class="legend-glyph" src="/assets/almanack/visibility-glyphs/masters/telescope.svg" alt="Telescope glyph"> Telescope</span>
  </div>
  <p class="legend-explanation"><strong>V</strong> followed by a number is visual magnitude; smaller or more negative numbers are brighter. If no observing-aid glyph is shown, the Almanack is not assigning an observing aid for that entry.</p>

  <p><strong>Events</strong></p>
  <div class="legend-line">
    <span class="legend-item"><img class="legend-glyph" src="/assets/almanack/visibility-glyphs/masters/meteor-shower.svg" alt="Meteor-shower glyph"> Meteor shower</span>
    <span class="legend-item"><img class="legend-glyph" src="/assets/almanack/visibility-glyphs/masters/solar-eclipse.svg" alt="Solar-eclipse glyph"> Solar eclipse</span>
    <span class="legend-item"><img class="legend-glyph" src="/assets/almanack/visibility-glyphs/masters/lunar-eclipse.svg" alt="Lunar-eclipse glyph"> Lunar eclipse</span>
  </div>

  <p><strong>Greek alphabet</strong> — Bayer letters used to identify stars within a constellation.</p>
  <div class="legend-line">
    <span class="legend-item">α Alpha</span><span class="legend-item">β Beta</span><span class="legend-item">γ Gamma</span><span class="legend-item">δ Delta</span><span class="legend-item">ε Epsilon</span><span class="legend-item">ζ Zeta</span><span class="legend-item">η Eta</span><span class="legend-item">θ Theta</span><span class="legend-item">ι Iota</span><span class="legend-item">κ Kappa</span><span class="legend-item">λ Lambda</span><span class="legend-item">μ Mu</span><span class="legend-item">ν Nu</span><span class="legend-item">ξ Xi</span><span class="legend-item">ο Omicron</span><span class="legend-item">π Pi</span><span class="legend-item">ρ Rho</span><span class="legend-item">σ Sigma</span><span class="legend-item">τ Tau</span><span class="legend-item">υ Upsilon</span><span class="legend-item">φ Phi</span><span class="legend-item">χ Chi</span><span class="legend-item">ψ Psi</span><span class="legend-item">ω Omega</span>
  </div>

  <p><strong>Zodiac</strong> — the 12 zodiac constellations/signs used for zodiac-day notation.</p>
  <div class="legend-line">
    <span class="legend-item"><span class="text-symbol">♈&#xfe0e;</span> Aries</span><span class="legend-item"><span class="text-symbol">♉&#xfe0e;</span> Taurus</span><span class="legend-item"><span class="text-symbol">♊&#xfe0e;</span> Gemini</span><span class="legend-item"><span class="text-symbol">♋&#xfe0e;</span> Cancer</span><span class="legend-item"><span class="text-symbol">♌&#xfe0e;</span> Leo</span><span class="legend-item"><span class="text-symbol">♍&#xfe0e;</span> Virgo</span><span class="legend-item"><span class="text-symbol">♎&#xfe0e;</span> Libra</span><span class="legend-item"><span class="text-symbol">♏&#xfe0e;</span> Scorpio</span><span class="legend-item"><span class="text-symbol">♐&#xfe0e;</span> Sagittarius</span><span class="legend-item"><span class="text-symbol">♑&#xfe0e;</span> Capricorn</span><span class="legend-item"><span class="text-symbol">♒&#xfe0e;</span> Aquarius</span><span class="legend-item"><span class="text-symbol">♓&#xfe0e;</span> Pisces</span>
  </div>

  <p><strong>Ephemerides</strong> — symbols identifying solar-system bodies in the positional tables.</p>
  <div class="legend-line">
    <span class="legend-item"><span class="text-symbol">☉&#xfe0e;</span> Sun</span><span class="legend-item"><span class="text-symbol">☽&#xfe0e;</span> Moon</span><span class="legend-item"><span class="text-symbol">☿&#xfe0e;</span> Mercury</span><span class="legend-item"><span class="text-symbol">♀&#xfe0e;</span> Venus</span><span class="legend-item"><span class="text-symbol">♂&#xfe0e;</span> Mars</span><span class="legend-item"><span class="text-symbol">⚳&#xfe0e;</span> Ceres</span><span class="legend-item"><span class="text-symbol">♃&#xfe0e;</span> Jupiter</span><span class="legend-item"><span class="text-symbol">♄&#xfe0e;</span> Saturn</span><span class="legend-item"><span class="text-symbol">♅&#xfe0e;</span> Uranus</span><span class="legend-item"><span class="text-symbol">♆&#xfe0e;</span> Neptune</span><span class="legend-item"><span class="text-symbol">♇&#xfe0e;</span> Pluto</span>
  </div>
</aside>"""

STYLE_RE = re.compile(r'<style id="almanack-legend-css">.*?</style>', re.S)
LEGEND_RE = re.compile(r'<aside class="notation-legend".*?</aside>', re.S)


def requested_years() -> tuple[int, ...]:
    if len(sys.argv) > 1:
        years = tuple(dict.fromkeys(int(arg) for arg in sys.argv[1:]))
        if any(year < 1900 or year > 2100 for year in years):
            raise SystemExit("Years must be in range 1900-2100")
        return years

    discovered = {
        int(path.name)
        for base in BASES
        if base.is_dir()
        for path in base.iterdir()
        if path.is_dir() and re.fullmatch(r"\d{4}", path.name)
    }
    return tuple(sorted(discovered))


def wire_page(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    text = STYLE_RE.sub("", original)
    text = LEGEND_RE.sub("", text)

    if "</head>" not in text or "</body>" not in text:
        raise RuntimeError(f"unexpected Almanack page shell: {path}")

    text = text.replace("</head>", STYLE + "</head>", 1)

    if "<footer" in text:
        text = text.replace("<footer", LEGEND + "<footer", 1)
    else:
        text = text.replace("</body>", LEGEND + "</body>", 1)

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    years = requested_years()
    changed = 0
    for base in BASES:
        for year in years:
            year_root = base / str(year)
            if not year_root.is_dir():
                continue
            for path in sorted(year_root.glob("W??/index.html")):
                if wire_page(path):
                    changed += 1
    print(f"Wired complete Almanack legend on {changed} weekly page copies for {' '.join(map(str, years))}")


if __name__ == "__main__":
    main()
