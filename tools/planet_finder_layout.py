#!/usr/bin/env python3
"""Install the canonical single-slot layout for Planet Finder artwork."""
from __future__ import annotations

import re
from pathlib import Path

STYLE_ID = "planet-finder-layout-css"
STYLE = f'''<style id="{STYLE_ID}">
.planet-finder-strip,
.w15-finder-strip {{ margin:1.25rem 0 2rem; max-width:100%; min-width:0; }}
.planet-finder-strip figure,
.w15-finder-strip figure {{ display:none; margin:0 auto; max-width:820px; }}
.planet-finder-strip figure.is-active,
.w15-finder-strip figure.is-active {{ display:block; }}
.planet-finder-strip img,
.w15-finder-strip img {{ display:block; width:100%; height:auto; }}
.planet-finder-strip figcaption,
.w15-finder-strip figcaption {{ text-align:center; font-family:system-ui,sans-serif; font-size:.82rem; color:var(--muted); margin-top:.35rem; }}
</style>'''

STYLE_RE = re.compile(
    rf'<style\b[^>]*id="{re.escape(STYLE_ID)}"[^>]*>.*?</style>\s*',
    re.DOTALL,
)


def ensure_planet_finder_layout(text: str) -> str:
    """Return HTML with exactly one current Planet Finder style block."""
    text = STYLE_RE.sub("", text)
    pos = text.lower().find("</head>")
    if pos < 0:
        raise ValueError("HTML has no </head> for Planet Finder layout")
    return text[:pos] + STYLE + "\n" + text[pos:]


def patch_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = ensure_planet_finder_layout(original)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True
