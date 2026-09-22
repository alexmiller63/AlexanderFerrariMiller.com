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


### 2026-09-22 — #2 artwork null placeholder

**State:** Fixed — awaiting verification
**Component:** Sky Notes descriptor-first generator

**Observed:** The descriptor-first generator wrote a week-owned `artwork: null` field when no artwork existed.

**Diagnosis:** `main()` explicitly assigned `payload["artwork"] = None`, contradicting the object-owned artwork contract. The generator's `generated_note()` path already removed the field correctly.

**Fix:** Replaced the explicit null assignment with `payload.pop("artwork", None)`. Commit: `3fa3df9030ee9152dfb8b659754cb739abe40ac2`.

**Verification:** Pending a generator run and inspection of generated JSON.

**Resolution:** Pending.


### 2026-09-22 — BUG-003 observing modes omit magnitude and misuse visibility marker

**State:** Open
**Discovered:** 2026-09-22
**Component:** Observing modes / fixed-object observing presentation

**Observed:** The observing-mode display does not show the object's magnitude. The “V” visibility marker is also displayed regardless of whether the star is actually visible.

**Diagnosis:** Pending.

**Fix:** Pending. The observing-mode output must include the magnitude, and the “V” marker must be conditional on actual visibility.

**Verification:** Pending.

**Resolution:** Pending.

**History:**
- 2026-09-22 — Reported during W36 visual review.

### 2026-09-22 — Observing mode omits stellar magnitude

**State:** Open
**Discovered:** 2026-09-22
**Component:** Observing modes / fixed-object display

**Observed:** The observing-mode display does not show the star's magnitude.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — V marker shown when star is not visible

**State:** Open
**Discovered:** 2026-09-22
**Component:** Observing modes / visibility display

**Observed:** The V visibility marker is displayed all the time. It should appear only when the star is actually visible.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Greek/Symbols solar-glare display bug

**State:** Open
**Discovered:** 2026-09-22
**Component:** Greek/Symbols observing mode / solar-glare display

**Observed:** There is a bug in the Greek/Symbols mode when an object is classified as Solar Glare. Exact incorrect display behavior is pending clarification.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Greek/Symbols solar-glare display includes text

**State:** Open
**Discovered:** 2026-09-22
**Component:** Ephemeris observing display / Greek/Symbols mode

**Observed:** In Greek/Symbols mode, a solar-glare condition displays both the solar-glare symbol and the words “Solar Glare”. The Greek/Symbols mode should display the symbol only.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Latin mode renders naked-eye as a glyph

**State:** Open
**Discovered:** 2026-09-22
**Component:** Observing modes / Latin mode

**Observed:** In Latin mode, the naked-eye observing classification is rendered as a glyph. It should use the Latin/text representation instead.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Mixed Learner naked-eye glyph lacks text

**State:** Open
**Discovered:** 2026-09-22
**Component:** Observing modes / Mixed Learner mode

**Observed:** In Mixed Learner mode, the naked-eye observing classification shows the eye glyph without its accompanying text.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Legend sentences run together

**State:** Open
**Discovered:** 2026-09-22
**Component:** Legend / explanatory text

**Observed:** Each sentence in the legend should appear on its own line. The current presentation runs multiple sentences together instead of giving each sentence its own line.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Legend sentences run together

**State:** Open
**Discovered:** 2026-09-22
**Component:** Legend / presentation

**Observed:** Each legend sentence currently runs together as a single paragraph. Each sentence should appear on its own line.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Observer time should be an explicit Local Apparent Time input

**State:** Open
**Discovered:** 2026-09-22
**Component:** Planetary observing status / observer controls

**Observed:** The website has an observer-latitude input but the observing calculation uses a fixed 21:00 Local Apparent Time snapshot. Observer time should also be explicitly represented as Local Apparent Time so observing status can be evaluated for the observer's selected time.

**Diagnosis:** Current specification hard-codes 21:00 LAT for the website observing snapshot.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Aries zero-degree label encroaches on chart rim

**State:** Open
**Discovered:** 2026-09-22
**Component:** Planet Finder chart / zodiac labels

**Observed:** The “Aries 0°” label, positioned between Pisces and Aries, encroaches on the chart rim.

**Expected:** The label should be positioned to the left of the chart, clear of the rim.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Highlights/Wordy control does not look like a toggle

**State:** Open
**Discovered:** 2026-09-22
**Component:** Sky Notes / Highlights–Wordy control

**Observed:** The Highlights/Wordy control does not visually communicate that it is a toggle.

**Expected:** It should have clear toggle affordance and state indication.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Altair chart title format is incorrect

**State:** Open
**Discovered:** 2026-09-22
**Component:** Sky Notes / fixed-object chart titles

**Observed:** The Altair in Aquila chart title does not use the required target-title format.

**Expected:** The title should read **“Alpha AQL, Altair in Aquila”**.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Fixed-star labels collide with constellation and asterism lines

**State:** Open
**Discovered:** 2026-09-22
**Component:** Sky Notes / fixed-object charts / label placement

**Observed:** Greek-letter star labels in the chart encroach on or collide with constellation lines and asterism lines.

**Expected:** Star labels should remain clear of both constellation and asterism linework.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Aquila constellation title collides with constellation lines

**State:** Open
**Discovered:** 2026-09-22
**Component:** Sky Notes / fixed-object charts / constellation labels

**Observed:** The constellation title “Aquila” overlaps or collides with the constellation linework.

**Expected:** The constellation title should be positioned clear of the constellation lines.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Encroaching constellation label crosses into neighboring boundary

**State:** Open
**Discovered:** 2026-09-22
**Component:** Sky Notes / fixed-object charts / constellation boundary labels

**Observed:** In the Altair in Aquila chart, the Delphinus constellation label does not fit within its own IAU boundary and encroaches into the neighboring Aquila boundary.

**Expected:** A constellation label should remain visually contained within its own boundary; when there is insufficient room, the rendering system should use an appropriate alternative placement rather than crossing the neighboring boundary.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.

### 2026-09-22 — Boundary label should fall back to three-letter designation

**State:** Open
**Discovered:** 2026-09-22
**Component:** Sky Notes / fixed-object charts / IAU boundary labels

**Observed:** In the Altair chart, the full constellation name “Delphinus” does not fit within its own IAU boundary and encroaches into the neighboring Aquila boundary.

**Expected:** When a full constellation name cannot fit within its own boundary without encroachment, fall back to the three-letter IAU designation. For this case, use **DEL** within the Delphinus boundary.

**Diagnosis:** Pending.

**Fix:** Pending.

**Verification:** Pending.

**Resolution:** Pending.
