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
GLYPH_ROOT = "/assets/almanack/visibility-glyphs/masters/"
WEEKLY_GLYPH_ROOT = "../../../assets/almanack/visibility-glyphs/masters/"

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
.greek-letter {
  display:inline-block;
  font-size:2em;
  line-height:.75;
  vertical-align:-.12em;
}
/* Notation items can render either symbols or words. Keep the container at
   ordinary text size, then enlarge only the leading astronomical symbol when
   Greek/Symbols or Mixed Learner mode is active. Latin mode therefore never
   enlarges the first letter of a word such as Capricorn or Beta. */
.ephemeris-notation-item,
.calendar-notation-item,
.notation-item,
.zodiac-glyph.notation-item {
  display:inline-block;
  font-size:1em;
  line-height:inherit;
  vertical-align:baseline;
  font-family:inherit;
}
body:not(:has([data-bayer-mode="latin"][aria-pressed="true"])) .ephemeris-notation-item::first-letter,
body:not(:has([data-bayer-mode="latin"][aria-pressed="true"])) .calendar-notation-item::first-letter,
body:not(:has([data-bayer-mode="latin"][aria-pressed="true"])) .notation-item::first-letter {
  font-family:'Apple Symbols','Arial Unicode MS','Segoe UI Symbol','Noto Sans Symbols 2',serif;
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
/* One canonical size for every observing/event glyph. */
.visibility-glyph { height:3em !important; width:auto !important; vertical-align:-.78em !important; }
.legend-glyph { height:3em; width:auto; vertical-align:-.78em; margin-right:.2rem; }
.ephemeris-visibility .text-symbol { font-size:3em; line-height:.7; vertical-align:-.2em; }
.legend-explanation { white-space:normal; }

/* Extended ephemerides always use one four-column grid.  Width belongs only to
   actual four-column cells; row-spanning headers such as Observing must keep
   their natural colspan width. */
table.extended-ephemeris {
  display:table;
  width:100%;
  table-layout:fixed;
}
table.extended-ephemeris th,
table.extended-ephemeris td {
  min-width:0;
  text-align:center;
}
table.extended-ephemeris thead th,
table.extended-ephemeris tbody td {
  width:25%;
}
table.extended-ephemeris th {
  overflow-wrap:anywhere;
}
table.extended-ephemeris td,
table.extended-ephemeris small {
  white-space:nowrap;
}
@media (max-width:760px) {
  table.extended-ephemeris {
    display:table !important;
    width:100% !important;
    table-layout:fixed !important;
    overflow:visible !important;
  }
  table.extended-ephemeris th,
  table.extended-ephemeris td {
    min-width:0 !important;
    padding:.55rem .25rem !important;
  }
  table.extended-ephemeris thead th,
  table.extended-ephemeris tbody td {
    width:25% !important;
  }
  table.extended-ephemeris th { font-size:.78rem; }
  table.extended-ephemeris td { font-size:.78rem; }
  table.extended-ephemeris .ephemeris-symbol { font-size:1.55em; }
  table.extended-ephemeris .visibility-glyph {
    max-width:100%;
    height:2.4em !important;
    object-fit:contain;
  }
}
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
    <span class="legend-item"><span class="greek-letter">α</span> Alpha</span><span class="legend-item"><span class="greek-letter">β</span> Beta</span><span class="legend-item"><span class="greek-letter">γ</span> Gamma</span><span class="legend-item"><span class="greek-letter">δ</span> Delta</span><span class="legend-item"><span class="greek-letter">ε</span> Epsilon</span><span class="legend-item"><span class="greek-letter">ζ</span> Zeta</span><span class="legend-item"><span class="greek-letter">η</span> Eta</span><span class="legend-item"><span class="greek-letter">θ</span> Theta</span><span class="legend-item"><span class="greek-letter">ι</span> Iota</span><span class="legend-item"><span class="greek-letter">κ</span> Kappa</span><span class="legend-item"><span class="greek-letter">λ</span> Lambda</span><span class="legend-item"><span class="greek-letter">μ</span> Mu</span><span class="legend-item"><span class="greek-letter">ν</span> Nu</span><span class="legend-item"><span class="greek-letter">ξ</span> Xi</span><span class="legend-item"><span class="greek-letter">ο</span> Omicron</span><span class="legend-item"><span class="greek-letter">π</span> Pi</span><span class="legend-item"><span class="greek-letter">ρ</span> Rho</span><span class="legend-item"><span class="greek-letter">σ</span> Sigma</span><span class="legend-item"><span class="greek-letter">τ</span> Tau</span><span class="legend-item"><span class="greek-letter">υ</span> Upsilon</span><span class="legend-item"><span class="greek-letter">φ</span> Phi</span><span class="legend-item"><span class="greek-letter">χ</span> Chi</span><span class="legend-item"><span class="greek-letter">ψ</span> Psi</span><span class="legend-item"><span class="greek-letter">ω</span> Omega</span>
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
GREEK_SPAN_RE = re.compile(r'<span class="greek-letter">([α-ω])</span>')
BAYER_EVENT_RE = re.compile(r'([α-ω])(?= [A-Z][a-z]{2}\b)')
BETA_LAT_RE = re.compile(r'(<small>)β(?= [−+\-])')
BETA_NOTE_RE = re.compile(r'(<strong>)β(?=</strong>)')


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

    # Normalize any previous run before adding the canonical Greek-letter markup.
    text = GREEK_SPAN_RE.sub(r"\1", text)
    text = BAYER_EVENT_RE.sub(r'<span class="greek-letter">\1</span>', text)
    text = BETA_LAT_RE.sub(r'\1<span class="greek-letter">β</span>', text)
    text = BETA_NOTE_RE.sub(r'\1<span class="greek-letter">β</span>', text)

    if "</head>" not in text or "</body>" not in text:
        raise RuntimeError(f"unexpected Almanack page shell: {path}")

    text = text.replace("</head>", STYLE + "</head>", 1)

    if "<footer" in text:
        text = text.replace("<footer", LEGEND + "<footer", 1)
    else:
        text = text.replace("</body>", LEGEND + "</body>", 1)

    # Weekly pages live at YEAR/WEEK/index.html.  A root-absolute /assets URL
    # works on the custom domain but misses the repository prefix on GitHub
    # Pages.  This relative path resolves to the same checked-in asset directory
    # in both deployments, so every observing/event glyph uses one portable path.
    text = text.replace(f'src="{GLYPH_ROOT}', f'src="{WEEKLY_GLYPH_ROOT}')

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
