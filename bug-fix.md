# Star Almanack Bug Fix Log

Ongoing log of bugs, bug state, fixes, and resolutions.

Use this file for defect tracking and bug-fix work. Keep architectural discussions and design notes in `notes.md`.

## Logging rules

- Append new bugs and discoveries; do not replace prior history.
- Give each bug a stable identifier.
- Record the bug state as it changes.
- Record the affected component, observed behavior, diagnosis, fix, verification, and resolution when known.
- Preserve failed fixes and regressions as part of the history.
- A bug is not resolved merely because code was changed; record the verification that established the resolution.
- Fix generators and sources rather than patching generated output whenever the defect originates upstream.

## Bug states

Use: **Open**, **Diagnosing**, **Fix in progress**, **Fixed — awaiting verification**, **Resolved**, **Regressed**, or **Deferred**.

## Entries

<!--
### BUG-001 — Short descriptive title

**State:** Open
**Discovered:** YYYY-MM-DD
**Component:** component or workflow

**Observed:** What is wrong.

**Diagnosis:** Root cause or current diagnostic evidence.

**Fix:** What was changed, including commit when available.

**Verification:** What was checked and the result.

**Resolution:** Final outcome, or "Pending" while unresolved.

**History:**
- YYYY-MM-DD — State change or significant discovery.
-->

## 2026-09-18 — Consolidated fix log recovered from W36–W40 review

This entry preserves the known fixes and architectural decisions accumulated during the W36–W40 review. Treat it as an ongoing checklist; append new discoveries rather than replacing this entry.

### Sky Notes and object relationships

- Sky Notes must not require Artwork Generator output to exist. Sky Notes and Artwork must not form a circular dependency.
- Sky Notes is upstream of artwork consumption: it may describe an object and its machine-readable identity without requiring artwork to have already been generated.
- Do not emit a week-level `artwork: null` placeholder when artwork is absent. Omit the field.
- “Other objects listed this week” is the intended meaning for the machine-readable object list. These are objects mentioned in the week, not necessarily objects physically or semantically “related” to the primary object.
- Other listed objects should link to their canonical object artwork/story target rather than embedding artwork in the Sky Note.
- Artwork is canonical/object-owned, not week-owned.
- Descriptor prose, machine-readable identity, and artwork must resolve through the canonical fixed-object identity rather than ad-hoc weekly slugs.
- The naked-eye item should not acquire an unrelated or redundant descriptor.

### Fixed-object descriptors and stories

- Diagnose missing descriptor fields in the source/population generator; do not patch generated weekly HTML.
- The canonical content chain is object identity → descriptor → prose/story → artwork → canonical URL.
- Dumbbell/M27 artwork was working but its diagnostic descriptor was missing; preserve this as a source-data/generator completeness check.
- Messier artwork generation was working; other referenced fixed objects had descriptors but missing artwork and therefore require completeness validation.
- Verify both human-readable prose and machine-readable object references, including Beta Sagittae (Sge).

### Sagitta (Sge)

- Use the canonical constellation name/abbreviation consistently: Sagitta (Sge).
- W36 fixed-object context includes Alpha Sagittae (α Sge), Sham.
- Beta Sagittae is a distinct object from M71 and must not be conflated with it.
- Beta Sagittae’s proper name is Shakh.
- Where the finder/chart context calls for the constellation, use “Sagitta, Sge” for the in-figure label and “M71 in Sagitta (Sge)” for the chart title.
- Legend convention: named star uses Bayer letter plus proper name (for example, “α — Sham”); unnamed star uses Bayer designation plus constellation abbreviation (for example, “β Sge”).
- The Sge identity mapping must be source-driven and must not be recreated by special-case weekly patches.

### Constellation geometry and labels

- Mensa (Men) and Microscopium (Mic) legitimately have accepted constellation boundaries but no stick figures. A missing stick figure is not a geometry-generation failure.
- The finder geometry adapter was changed so an accepted constellation with `has_figure: false` returns no stick-figure paths instead of raising. Commit: `f91b2dd`.
- Do not invent replacement stick figures for Mensa or Microscopium.
- Boundary geometry remains valid and must remain available to collision/label logic even when stick-figure geometry is absent.
- When a full constellation name cannot be placed collision-free, first try the three-letter designation; only if that also cannot fit should the label be omitted.
- If another constellation’s boundary encroaches on an otherwise usable label position, the collision diagnostic should identify the encroaching constellation by name.
- Leader-line collisions remain a major geometry/layout cleanup area.
- Placement search should be systematic and recursive rather than relying on brittle special cases.
- The intended next-step search architecture is dynamic most-constrained-first backtracking: at each recursion level consider the remaining object with the fewest viable placements first, while retaining the ability to backtrack through alternative object orders and placements (“the squeaky wheel gets the grease”).
- Geometry fixes belong in the generator/source geometry layer, not as post-generation patches.

### Artwork and generator behavior

- Artwork Generator owns the geometry/artwork contract; descriptors should not be responsible for inventing or repairing geometry.
- Artwork generation must validate canonical object identity and required descriptive fields rather than accepting false-positive completeness.
- Generated artwork must be validated by the downstream acceptance/Chromium verification stage; a green source-generation step alone is not proof of a valid deployed result.
- Remove obsolete legacy weekly finder artifacts rather than preserving duplicate representations. The legacy main W36 finder was identified for removal.
- Keep generation idempotent and fix the generator/source of the defect rather than patching individual generated pages.

### Previously established presentation fixes retained in this log

- Latin and Mixed Learner observing-aid modes must contain their actual text, not only the Greek/Symbol representation.
- Naked-eye uses the eye glyph; binoculars use the binoculars glyph rather than the letter B; substantial-telescope uses the two-telescope glyph.
- Sun observing text is “visible”; daylight and solar glare are distinct observing states.
- Ceres and Pluto require observer glyphs; Pluto is “substantial telescope.”
- Ephemeris body ordering is Sun, Mercury, Venus, Earth, Moon, Mars, Ceres, Jupiter, Saturn, Uranus, Neptune, Pluto.
- Constellation naming preserves traditional equinox names, including First Point of Aries and First Point of Libra.
- Pleiades wording: “open cluster in Taurus (also an asterism).”
- Week navigation must work across year boundaries, with correct first/last-week behavior and matching top/bottom navigation.
- On a week page, only the week should be highlighted in the navigation; the current year should not be independently highlighted.
- Star-hops/guiding routes are curated established routes and should be represented as prose plus machine-readable relationships; do not invent or scrape arbitrary routes.
- Milky Way visibility uses named regions rather than a single generic “in Milky Way” classification; region geometry is machine-readable and validated.
- Constellation identity comprises all 89 IAU constellations; Serpens is represented as Caput and Cauda where applicable.
