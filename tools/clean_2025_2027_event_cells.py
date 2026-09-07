#!/usr/bin/env python3
"""Clear all calendar Events cells for 2025 and 2027 before canonical regeneration."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
for base in (ROOT / "Star-Almanack-Repo" / "site", ROOT / "almanack"):
    for year in (2025, 2027):
        for page in (base / str(year)).glob("W*/index.html"):
            text = page.read_text(encoding="utf-8")
            new = re.sub(r'(<tr><td>.*?</td><td>.*?</td><td>).*?(</td></tr>)', r'\1—\2', text)
            if new != text:
                page.write_text(new, encoding="utf-8")
                print(page)
