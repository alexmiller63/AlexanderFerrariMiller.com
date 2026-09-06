#!/usr/bin/env python3
"""Build the expanded 2026 Almanack from the integrated calendar and full fixed-object catalogs."""
from datetime import date, datetime, timedelta
from pathlib import Path
import csv
import re

ROOT = Path(__file__).parent
calendar = (ROOT / "almanack.md").read_text(encoding="utf-8")
source = (ROOT / "ISO2026.md").read_text(encoding="utf-8")
bayer_text = (ROOT / "expanded-bayer-visibility-2026.csv").read_text(encoding="utf-8")
bright_text = (ROOT / "bright-star-visibility-2026.csv").read_text(encoding="utf-8")

legacy_intro = """## Working Integrated Almanack

This working edition integrates the supplied 2026 zodiac calendar, best-visibility dates for 100 selected stars and Messier objects, lunar phases, Wheel-of-the-Year points, named full moons, and the 53 weekly classical-planet snapshots.

Planetary positions are geocentric tropical ecliptic longitudes sampled Monday at 00:00 UTC. Weekly chart filenames are reserved for later insertion using the approved chart model.

> **Validation status:** The source material reports 100/100 best-visibility calculations passing their recalculation check and all 50 lunar phases matching the USNO comparison. The 371 weekly planetary positions remain representatively checked rather than fully independently audited.
"""
expanded_intro = """## Working Integrated Almanack

This working edition covers the complete 53-week ISO 2026 week-year and integrates the supplied zodiac calendar, all 110 Messier objects, the audited α/β Bayer catalog, the second-magnitude naked-eye star layer, lunar phases, Wheel-of-the-Year points, named full moons, and weekly Solar-System snapshots.

Planetary positions are geocentric tropical ecliptic longitudes sampled Monday at 00:00 UTC. Fixed-object best-visibility dates use the Star Almanack observer-first visibility rule. Weekly chart filenames are reserved for later insertion using the approved chart model.

> **Validation status:** The generated expanded Almanack is checked by repository CI for all 53 ISO weeks and 371 civil-date rows, all 110 Messier objects on their computed best-visibility dates, fixed-object placement completeness, and the reconciled second-magnitude star layer. The source material also reports all 50 lunar phases matching the USNO comparison. The weekly planetary positions remain representatively checked rather than fully independently audited.
"""
if legacy_intro not in calendar:
    raise SystemExit("Expected legacy Almanack introduction was not found")
calendar = calendar.replace(legacy_intro, expanded_intro, 1)

with (ROOT / "expanded-bayer-visibility-2026.csv").open(encoding="utf-8", newline="") as f:
    bayer_rows = list(csv.DictReader(f))
with (ROOT / "messier-visibility-2026.csv").open(encoding="utf-8", newline="") as f:
    messier_rows = list(csv.DictReader(f))
with (ROOT / "bright-star-visibility-2026.csv").open(encoding="utf-8", newline="") as f:
    bright_rows = list(csv.DictReader(f))
bright_new_rows = [r for r in bright_rows if r.get("new_non_alpha_beta") == "yes"]

GREEK_BAYER_CODES = {
    "Alp": "α", "Bet": "β", "Gam": "γ", "Del": "δ", "Eps": "ε",
    "Zet": "ζ", "Eta": "η", "The": "θ", "Iot": "ι", "Kap": "κ",
    "Lam": "λ", "Mu": "μ", "Nu": "ν", "Xi": "ξ", "Omi": "ο",
    "Pi": "π", "Rho": "ρ", "Sig": "σ", "Tau": "τ", "Ups": "υ",
    "Phi": "φ", "Chi": "χ", "Psi": "ψ", "Ome": "ω",
}


def display_bayer_code(code):
    """Render HYG's Latin Bayer code with its Greek letter symbol."""
    code = code.strip()
    match = re.fullmatch(r"([A-Z][a-z]{2})(?:-?(\d+))?", code)
    if not match or match.group(1) not in GREEK_BAYER_CODES:
        return code
    return GREEK_BAYER_CODES[match.group(1)] + (match.group(2) or "")

ephemeris = {}
with (ROOT / "weekly-ephemeris-2026.csv").open(encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        ephemeris[row["iso_week"]] = row

expected = [f"ISO 2026-W{i:02d}" for i in range(1, 54)]
weeks = re.findall(r"(?m)^## (ISO 2026-W\d{2})\s*$", calendar)
if weeks != expected[:len(weeks)] or len(weeks) > 53:
    raise SystemExit(f"Unexpected weekly structure in almanack.md: {weeks[-5:]}")

if len(weeks) < 53:
    ingress = []
    for m in re.finditer(r"\| (♒|♓|♈|♉|♊|♋|♌|♍|♎|♏|♐|♑) \([^|]+\) \| \d+° \| (2026-\d\d-\d\d) (\d\d:\d\d:\d\d) \|", source):
        ingress.append((datetime.fromisoformat(f"{m.group(2)}T{m.group(3)}"), m.group(1)))
    ingress.sort()
    if len(ingress) != 12:
        raise SystemExit(f"Expected 12 zodiac ingresses, found {len(ingress)}")

    events = {}
    phase_re = re.compile(r"\| ([🌕🌗🌑🌓] [^|]+) \| (2026-\d\d-\d\d \d\d:\d\d:\d\d) \|")
    for m in phase_re.finditer(source):
        ts = datetime.fromisoformat(m.group(2))
        events.setdefault(ts.date(), []).append(f"{m.group(1)} — {ts:%H:%M:%S} UTC")

    def zodiac_for_day(d):
        boundaries = [(date(2025, 12, 21), "♑")] + [(ts.date(), sign) for ts, sign in ingress]
        last_date, sign = max((x for x in boundaries if x[0] <= d), key=lambda x: x[0])
        return sign, (d - last_date).days + 1

    def ephem_table(row):
        primary = [("☉ Sun", row["sun"]), ("☽ Moon", row["moon"]), ("☿ Mercury", row["mercury"]),
                   ("♀ Venus", row["venus"]), ("♂ Mars", row["mars"]), ("♃ Jupiter", row["jupiter"]),
                   ("♄ Saturn", row["saturn"])]
        extended = [("♅ Uranus", row["uranus"]), ("♆ Neptune", row["neptune"]), ("⚳ Ceres", row["ceres"])]

        def render(cols):
            return ("| " + " | ".join(x[0] for x in cols) + " |\n"
                    "|" + "|".join("---:" for _ in cols) + "|\n"
                    "| " + " | ".join(x[1] for x in cols) + " |")

        return render(primary) + "\n\n**Extended targets:**\n\n" + render(extended)

    sign_names = {"♈":"Aries","♉":"Taurus","♊":"Gemini","♋":"Cancer","♌":"Leo","♍":"Virgo",
                  "♎":"Libra","♏":"Scorpio","♐":"Sagittarius","♑":"Capricorn","♒":"Aquarius","♓":"Pisces"}
    additions = []
    for w in range(len(weeks) + 1, 54):
        key = f"2026-W{w:02d}"
        if key not in ephemeris:
            raise SystemExit(f"Missing weekly ephemeris for {key}")
        monday = date.fromisocalendar(2026, w, 1)
        sunday = monday + timedelta(days=6)
        rows = []
        for i in range(7):
            d = monday + timedelta(days=i)
            sign, daynum = zodiac_for_day(d)
            z = f"{sign} ({sign_names[sign]}) {daynum}" if daynum == 1 else f"{sign} {daynum}"
            ev = "<br>".join(events.get(d, ["—"]))
            rows.append(f"| {d:%a, %b %d, %Y} | {z} | {ev} |")
        additions.append(
            f"## ISO {key}\n\n"
            f"**ISO dates:** {key}-1 through {key}-7  \n\n"
            f"**Civil dates:** {monday:%b %d, %Y} – {sunday:%b %d, %Y}\n\n"
            "### Calendar\n\n| Date | Zodiac day | Events |\n|---|---|---|\n"
            + "\n".join(rows) + "\n\n"
            "### Weekly Solar-System Ephemeris\n\n"
            f"**Snapshot:** {monday:%B %-d, %Y} · 00:00 UTC\n\n"
            + ephem_table(ephemeris[key]) + "\n\n"
            "### Sky Note\n\nWeekly geocentric tropical planetary positions, sampled Monday at 00:00 UTC.\n\n"
            "### Chart\n\n"
            f"`ISO2026-W{w}-chart.png` — chart slot."
        )
    calendar = calendar.rstrip() + "\n\n" + "\n\n".join(additions)

# Markdown/Jekyll requires every row of a pipe table to be contiguous.  The
# legacy Almanack source contains blank lines between rows; remove only those
# blank lines so each weekly calendar and ephemeris renders as one table.
calendar = re.sub(r"(?m)^(\|[^\n]*\|)\n\n(?=\|)", r"\1\n", calendar)

# Build the complete fixed-object event set by civil date.  Each generated
# row carries conservative aliases used only to suppress a duplicate legacy
# calendar label.  Source rows always remain intact.  Bayer rows that share
# the same unnumbered designation on the same date may share one observer-facing
# target, while separately numbered designations such as α1/α2 remain distinct.
fixed = {}
for row in messier_rows:
    messier = row["messier"]
    fixed.setdefault(row["best_date"], []).append(
        (f"Messier:{messier}", f"Best visibility: {messier}", (messier,), f"Messier:{messier}")
    )


def bayer_placement_date(row):
    """Require the computed Bayer date to belong to ISO week-year 2026."""
    placement_date = row["best_date"]
    d = date.fromisoformat(placement_date)
    if d.isocalendar().year != 2026:
        raise SystemExit(
            f"Bayer visibility date outside ISO 2026: {row.get('bayer', row.get('bayer_code', '?'))} — {placement_date}"
        )
    return placement_date


# Pick the most informative display label for each Bayer observing target.
# This makes a duplicated physical/component source such as α Com render once
# as "Diadem (α Com)" while preserving every underlying catalog row.
bayer_target_labels = {}
for row in bayer_rows:
    designation = row["bayer"]
    proper = row.get("proper", "").strip()
    placement_date = bayer_placement_date(row)
    key = (placement_date, designation.casefold())
    label = f"{proper} ({designation})" if proper else designation
    current = bayer_target_labels.get(key)
    if current is None or (proper and current == designation):
        bayer_target_labels[key] = label

for idx, row in enumerate(bayer_rows):
    designation = row["bayer"]
    proper = row.get("proper", "").strip()
    placement_date = bayer_placement_date(row)
    target_key = f"BayerTarget:{placement_date}:{designation.casefold()}"
    label = bayer_target_labels[(placement_date, designation.casefold())]
    ident = f"Bayer:{idx}:{row['bayer_code']}:{row['con']}"
    aliases = tuple(x for x in (proper, designation) if x)
    fixed.setdefault(placement_date, []).append((ident, f"Best visibility: {label}", aliases, target_key))
for idx, row in enumerate(bright_new_rows):
    proper = (row.get("proper") or "").strip()
    bayer = display_bayer_code(row.get("bayer") or "")
    con = (row.get("con") or "").strip()
    name = proper or (f"{bayer} {con}".strip())
    mag_class = (row.get("mag_class") or "").strip()
    label = f"{name} — V{mag_class}" if mag_class else name
    ident = f"Bright:{idx}:{row.get('hyg_id','')}"
    aliases = tuple(x for x in (proper, bayer) if x)
    fixed.setdefault(row["best_date"], []).append((ident, f"Best visibility: {label}", aliases, ident))

seen = set()
row_re = re.compile(r"(?m)^(\| (?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), ([A-Z][a-z]{2}) (\d{2}), (2025|2026|2027) \| [^|]+ \| )([^|]*)( \|)$")
months = {m: i for i, m in enumerate(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], 1)}
messier_best_dates = {row["messier"].upper(): row["best_date"] for row in messier_rows}


def legacy_has_alias(existing, aliases):
    """Return True only for conservative identity matches in legacy text."""
    folded = existing.casefold()
    for alias in aliases:
        alias = alias.strip()
        if not alias:
            continue
        if re.fullmatch(r"M\d{1,3}", alias, flags=re.IGNORECASE):
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?!\d)", existing, flags=re.IGNORECASE):
                return True
        elif alias.casefold() in folded:
            return True
    return False


def reconcile_legacy_messier(match):
    """Keep each legacy Messier label only on the catalog's computed best date."""
    d = date(int(match.group(4)), months[match.group(2)], int(match.group(3))).isoformat()
    existing = match.group(5).strip()
    if existing in {"", "—"}:
        return match.group(0)
    parts = existing.split("<br>")
    kept = []
    for part in parts:
        m = re.search(r"(?<![A-Za-z0-9])(M\d{1,3})(?!\d)", part, flags=re.IGNORECASE)
        if part.startswith("Best visibility:") and m:
            canonical_date = messier_best_dates.get(m.group(1).upper())
            if canonical_date and canonical_date != d:
                continue
        kept.append(part)
    rendered = "<br>".join(kept) if kept else "—"
    return match.group(1) + rendered + match.group(6)


# Legacy source prose sometimes carried a Messier object's descriptive label
# on a neighboring date.  Reconcile those by M-number to the generated catalog
# date before injecting fixed-object rows, so the calendar has one occurrence.
calendar = row_re.sub(reconcile_legacy_messier, calendar)


def add_fixed(match):
    d = date(int(match.group(4)), months[match.group(2)], int(match.group(3))).isoformat()
    existing = match.group(5).strip()
    additions = []
    displayed_targets = set()
    for ident, text, aliases, target_key in fixed.get(d, []):
        if ident in seen:
            continue
        # Completeness accounting records every catalog row as placed even when
        # multiple source rows intentionally share one observer-facing target.
        seen.add(ident)
        if target_key in displayed_targets:
            continue
        if text in existing or legacy_has_alias(existing, aliases):
            displayed_targets.add(target_key)
            continue
        additions.append(text)
        displayed_targets.add(target_key)
    parts = [] if existing in {"", "—"} else existing.split("<br>")
    parts.extend(additions)
    rendered = "<br>".join(parts) if parts else "—"
    return match.group(1) + rendered + match.group(6)

calendar = row_re.sub(add_fixed, calendar)

# The Events column already supplies the context: keep object labels compact.
calendar = re.sub(r"(?<=\| )Best visibility: ", "", calendar)
calendar = calendar.replace("<br>Best visibility: ", "<br>")

if len(messier_rows) != 110:
    raise SystemExit(f"Expected 110 Messier rows, found {len(messier_rows)}")
if len(bright_rows) != 92:
    raise SystemExit(f"Expected 92 reconciled bright-star systems, found {len(bright_rows)}")
if len(bright_new_rows) != 41:
    raise SystemExit(f"Expected 41 new non-alpha/beta bright-star systems, found {len(bright_new_rows)}")
expected_fixed = len(messier_rows) + len(bayer_rows) + len(bright_new_rows)
if len(seen) != expected_fixed:
    raise SystemExit(f"Fixed-object placement incomplete: placed {len(seen)} of {expected_fixed}")

header = "# Star Almanack — 2026\n\n*A Natural Philosopher's Guide to the Night Sky*\n\n"
objects = (
    "## Expanded α and β Star Catalog\n\n"
    "The complete generated Bayer catalog for 2026 follows. Best-visibility dates are computed by the Star Almanack visibility rule.\n\n"
    + bayer_text
    + "\n\n## Second-Magnitude Bright-Star Catalog\n\n"
    "The reconciled naked-eye stellar-system catalog follows. Decimal V values are retained here for provenance; Almanack calendar entries use whole-number V classes.\n\n"
    + bright_text
)
out = header + calendar.rstrip() + "\n\n" + objects
(ROOT / "almanack-expanded.md").write_text(out, encoding="utf-8")
print(f"Built almanack-expanded.md: 53 ISO weeks; 110 Messier objects; {len(bayer_rows)} Bayer rows; {len(bright_new_rows)} new bright-star systems")
