#!/usr/bin/env python3
"""Install the canonical responsive layout rules for Star Almanack calendars."""
from __future__ import annotations

import re
from pathlib import Path

STYLE_ID = "calendar-mobile-layout-css"
STYLE = f'''<style id="{STYLE_ID}">
@media (max-width:760px) {{
  table.calendar {{ width:100%; table-layout:fixed; }}
  table.calendar th, table.calendar td {{ min-width:0; padding:.55rem .45rem; overflow-wrap:anywhere; word-break:normal; }}
  table.calendar th:first-child, table.calendar td:first-child {{ width:26%; }}
  table.calendar th:nth-child(2), table.calendar td:nth-child(2) {{ width:24%; }}
  table.calendar th:nth-child(3), table.calendar td:nth-child(3) {{ width:50%; }}
  table.calendar td:first-child {{ white-space:normal; }}
  table.calendar td:nth-child(2) {{ white-space:normal; text-align:center; }}
  table.calendar td.calendar-events-region,
  .calendar-events,
  .calendar-events .event-cell {{ min-width:0; max-width:100%; }}
  .calendar-events .event-cell {{ overflow-wrap:anywhere; word-break:normal; }}
  .visibility {{ white-space:normal; }}
}}
</style>'''

STYLE_RE = re.compile(
    rf'<style\b[^>]*id="{re.escape(STYLE_ID)}"[^>]*>.*?</style>\s*',
    re.DOTALL,
)


def ensure_mobile_layout(text: str) -> str:
    """Return HTML with exactly one current mobile-calendar style block."""
    text = STYLE_RE.sub("", text)
    pos = text.lower().find("</head>")
    if pos < 0:
        raise ValueError("HTML has no </head> for calendar mobile layout")
    return text[:pos] + STYLE + "\n" + text[pos:]


def patch_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = ensure_mobile_layout(original)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True
