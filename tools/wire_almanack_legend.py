#!/usr/bin/env python3
"""Ensure every Almanack weekly page has the same complete notation legend."""

from pathlib import Path
import re

ROOT = Path("almanack")
YEARS = (2025, 2026, 2027)

STYLE = """<style id="almanack-legend-css">
.notation-legend {
  max-width:1080px;
  margin:0 auto;
  padding:1rem 1.5rem 1.35rem;
  font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:.88rem;
}
.notation-legend p { max-width:none; }
.legend-line { display:flex; flex-wrap:wrap; gap:.45rem 1rem; }
.legend-item { white-space:nowrap; }
.text-symbol { font-size:1.05em; }
</style>"""

LEGEND = """<aside class="notation-legend" aria-label="Notation legend">
  <p><strong>Notation:</strong> Greek/Symbols uses astronomical symbols and Greek Bayer letters; Latin spells out names; Mixed Learner shows symbols together with their names.</p>
  <p class="legend-line">
    <span class="legend-item"><span class="text-symbol">☉</span> Sun</span>
    <span class="legend-item"><span class="text-symbol">☽</span> Moon</span>
    <span class="legend-item"><span class="text-symbol">☿</span> Mercury</span>
    <span class="legend-item"><span class="text-symbol">♀</span> Venus</span>
    <span class="legend-item"><span class="text-symbol">♂</span> Mars</span>
    <span class="legend-item"><span class="text-symbol">♃</span> Jupiter</span>
    <span class="legend-item"><span class="text-symbol">♄</span> Saturn</span>
    <span class="legend-item"><span class="text-symbol">♅</span> Uranus</span>
    <span class="legend-item"><span class="text-symbol">♆</span> Neptune</span>
    <span class="legend-item"><span class="text-symbol">⚳</span> Ceres</span>
    <span class="legend-item"><span class="text-symbol">♇</span> Pluto</span>
  </p>
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
    for year in YEARS:
        for path in sorted((ROOT / str(year)).glob("W??/index.html")):
            if wire_page(path):
                changed += 1
    print(f"Wired complete Almanack legend on {changed} weekly pages")


if __name__ == "__main__":
    main()
