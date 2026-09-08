#!/usr/bin/env python3
"""Ensure every Almanack weekly page has the same complete notation legend.

Canonical ephemeris-body legend order: Sun, Moon, Mercury, Venus, Mars, Ceres,
Jupiter, Saturn, Uranus, Neptune, Pluto.

This file is also the deployment trigger for refreshing stale static legends.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASES = (ROOT / "almanack", ROOT / "Star-Almanack-Repo" / "site")
YEARS = (2025, 2026, 2027)

STYLE = """<style id="almanack-legend-css">
.notation-legend {
  max-width:1080px;
  margin:0 auto;
  padding:1rem 1.5rem 1.35rem;
  font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:.88rem;
}
.notation-legend p { max-width:none; margin:.35rem 0; }
.legend-line { display:flex; flex-wrap:wrap; gap:.45rem 1rem; }
.legend-item { white-space:nowrap; }
.text-symbol { font-size:1.05em; font-variant-emoji:text; }
</style>"""

LEGEND = """<aside class="notation-legend" aria-label="Astronomical notation legend">
  <p><strong>Greek alphabet</strong></p>
  <div class="legend-line">
    <span class="legend-item">α Alpha</span><span class="legend-item">β Beta</span><span class="legend-item">γ Gamma</span><span class="legend-item">δ Delta</span><span class="legend-item">ε Epsilon</span><span class="legend-item">ζ Zeta</span><span class="legend-item">η Eta</span><span class="legend-item">θ Theta</span><span class="legend-item">ι Iota</span><span class="legend-item">κ Kappa</span><span class="legend-item">λ Lambda</span><span class="legend-item">μ Mu</span><span class="legend-item">ν Nu</span><span class="legend-item">ξ Xi</span><span class="legend-item">ο Omicron</span><span class="legend-item">π Pi</span><span class="legend-item">ρ Rho</span><span class="legend-item">σ Sigma</span><span class="legend-item">τ Tau</span><span class="legend-item">υ Upsilon</span><span class="legend-item">φ Phi</span><span class="legend-item">χ Chi</span><span class="legend-item">ψ Psi</span><span class="legend-item">ω Omega</span>
  </div>
  <p><strong>Zodiac</strong></p>
  <div class="legend-line">
    <span class="legend-item"><span class="text-symbol">♈&#xfe0e;</span> Aries</span><span class="legend-item"><span class="text-symbol">♉&#xfe0e;</span> Taurus</span><span class="legend-item"><span class="text-symbol">♊&#xfe0e;</span> Gemini</span><span class="legend-item"><span class="text-symbol">♋&#xfe0e;</span> Cancer</span><span class="legend-item"><span class="text-symbol">♌&#xfe0e;</span> Leo</span><span class="legend-item"><span class="text-symbol">♍&#xfe0e;</span> Virgo</span><span class="legend-item"><span class="text-symbol">♎&#xfe0e;</span> Libra</span><span class="legend-item"><span class="text-symbol">♏&#xfe0e;</span> Scorpio</span><span class="legend-item"><span class="text-symbol">♐&#xfe0e;</span> Sagittarius</span><span class="legend-item"><span class="text-symbol">♑&#xfe0e;</span> Capricorn</span><span class="legend-item"><span class="text-symbol">♒&#xfe0e;</span> Aquarius</span><span class="legend-item"><span class="text-symbol">♓&#xfe0e;</span> Pisces</span>
  </div>
  <p><strong>Ephemerides</strong></p>
  <div class="legend-line">
    <span class="legend-item"><span class="text-symbol">☉&#xfe0e;</span> Sun</span><span class="legend-item"><span class="text-symbol">☽&#xfe0e;</span> Moon</span><span class="legend-item"><span class="text-symbol">☿&#xfe0e;</span> Mercury</span><span class="legend-item"><span class="text-symbol">♀&#xfe0e;</span> Venus</span><span class="legend-item"><span class="text-symbol">♂&#xfe0e;</span> Mars</span><span class="legend-item"><span class="text-symbol">⚳&#xfe0e;</span> Ceres</span><span class="legend-item"><span class="text-symbol">♃&#xfe0e;</span> Jupiter</span><span class="legend-item"><span class="text-symbol">♄&#xfe0e;</span> Saturn</span><span class="legend-item"><span class="text-symbol">♅&#xfe0e;</span> Uranus</span><span class="legend-item"><span class="text-symbol">♆&#xfe0e;</span> Neptune</span><span class="legend-item"><span class="text-symbol">♇&#xfe0e;</span> Pluto</span>
  </div>
</aside>"""

STYLE_RE = re.compile(r'<style id="almanack-legend-css">.*?</style>', re.S)
LEGEND_RE = re.compile(r'<aside class="notation-legend".*?</aside>', re.S)


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
    changed = 0
    for base in BASES:
        for year in YEARS:
            for path in sorted((base / str(year)).glob("W??/index.html")):
                if wire_page(path):
                    changed += 1
    print(f"Wired complete Almanack legend on {changed} weekly page copies")


if __name__ == "__main__":
    main()
