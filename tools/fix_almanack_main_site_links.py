#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
changed = 0

for path in sorted((ROOT / "almanack").glob("20[0-9][0-9]/index.html")):
    text = path.read_text(encoding="utf-8")
    new = text.replace('<a href="/index.html">Main Site</a>', '<a href="../../index.html">Main Site</a>')
    if new != text:
        path.write_text(new, encoding="utf-8")
        changed += 1

for path in sorted((ROOT / "almanack").glob("20[0-9][0-9]/W[0-9][0-9]/index.html")):
    text = path.read_text(encoding="utf-8")
    new = text.replace('<a href="/index.html">Main Site</a>', '<a href="../../../index.html">Main Site</a>')
    if new != text:
        path.write_text(new, encoding="utf-8")
        changed += 1

print(f"Fixed Main Site link on {changed} Almanack pages")
