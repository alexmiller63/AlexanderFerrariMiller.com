# Star Almanack Notes

Continuous project log. Append new entries; do not rewrite prior entries except to correct a documented factual error.

## 2026-09-02 — Expanded 2026 Almanack and Bayer audit

The expanded 2026 Star Almanack now covers the complete ISO 2026 week-year, W01 through W53. ISO 2026 extends beyond the Gregorian year boundary into January 2027; this matters for fixed-object placement. In particular, β Reticuli has a computed best-visibility instant on 2026-12-31 20:05 UTC that rounds to 2027-01-01, which is still ISO 2026-W53-5. The builder was corrected to treat the Almanack as an ISO week-year rather than restricting event injection to Gregorian dates whose year field is 2026.

The fixed-object integration target is all 110 Messier objects plus all catalogued α and β Bayer-designated stars, with separately numbered components retained when appropriate. The successful expanded build currently contains 110 Messier objects and 159 α/β Bayer rows distributed onto the 53 weekly calendar pages by the preserved best-visibility rule.

Bayer completeness is not defined as “every constellation must have both α and β.” Historical Bayer lettering, later constellation boundaries, and the breakup of Argo Navis create legitimate absences. Therefore, missing α/β entries must be audited rather than blindly filled.

Current source-catalog gaps found in the 159-row α/β catalog:

- No α entry: Canes Venatici, Capricornus, Centaurus, Crux, Hercules, Leo Minor, Libra, Norma, Puppis, Vela.
- No β entry: Antlia, Lynx, Norma, Puppis, Sagittarius, Scorpius, Telescopium, Tucana, Vela, Vulpecula.

Working justification rule for future additions:

1. Add an α or β entry only when the Bayer designation is explicitly supported by an authoritative astronomical source, preferably SIMBAD/CDS or another primary/standard catalog.
2. Preserve legitimate historical absences and document why they are absent.
3. Retain separately designated numbered components such as α¹/α² or β¹/β² when the designation is genuinely separate rather than silently collapsing them.
4. Keep the Bayer designation as the stable identity for completeness checking; proper names are supplementary.
5. Do not weaken completeness checks to make a build pass. Resolve catalog, ISO-year, or parsing issues directly.

Initial audit indicates that several current gaps are real catalog omissions rather than legitimate absences. Candidates requiring authoritative confirmation and then addition include α Canum Venaticorum / Cor Caroli components, α Capricorni components, α Centauri, α Crucis components, α Herculis components, α Librae components, β Sagittarii components, β Scorpii components, and β Tucanae components. Conversely, some constellations legitimately lack a modern α or β Bayer designation; examples already identified include Leo Minor, Norma, Puppis, and Vela for α, with several β absences tied to historical boundary changes or incomplete Bayer lettering.

The standard going forward is defensibility and reproducibility: every added Bayer entry should have a traceable astronomical justification, and every intentional gap should be explainable.

## 2026-09-02 — Authoritative gap audit, first pass

The first authoritative cross-check confirms that the current 159-row source catalog is missing genuine Bayer-designated systems. These are not inferred from constellation naming conventions; they are supported by SIMBAD/CDS identifiers or catalog-backed coordinate records.

Confirmed omissions to add:

- α¹ and α² Canum Venaticorum. SIMBAD explicitly identifies α¹ CVn (HD 112412) and α² CVn / Cor Caroli (HD 112413).
- α¹ and α² Capricorni. SIMBAD recognizes the α Capricorni pair and specifically resolves α² Cap; catalog-backed astrometry separately identifies α¹ Cap.
- α Centauri. SIMBAD explicitly recognizes α Cen A and α Cen B; the Bayer identity belongs to the Alpha Centauri system rather than to a missing modern constellation letter.
- α¹ and α² Crucis. Catalog-backed records explicitly identify Alpha1 Crucis and Alpha2 Crucis; α¹ is Acrux.
- α¹ and α² Herculis. SIMBAD identifies α Her as a multiple system and the Washington Double Star Catalog resolves Alpha1 Herculis and Alpha2 Herculis.
- α¹ and α² Librae. Standard catalog records explicitly identify both numbered Bayer components.
- β¹ and β² Sagittarii. SIMBAD-backed records explicitly identify β¹ Sgr and β² Sgr.
- β¹ and β² Scorpii. Standard catalog records explicitly identify both numbered Bayer components.
- β¹ and β² Tucanae. Standard catalog records explicitly identify both numbered Bayer components.

These entries should be added as numbered Bayer entries where numbering is part of the designation. α Centauri should not be artificially converted into α¹/α²; A and B are stellar components of the α Cen system, not numbered Bayer designations.

Legitimate gaps remain legitimate and should stay absent unless contrary catalog evidence is found. The audit therefore distinguishes “no α/β exists in the modern Bayer scheme” from “our source extraction missed an existing Bayer designation.”

Next implementation step: add a small auditable supplemental Bayer source for the confirmed omissions, carrying source provenance and coordinates, then feed that supplement through the same 2026 best-visibility computation and completeness checks instead of editing generated output by hand.

## 2026-09-02 — Bright-star variability and star-note policy

For a future Bright 50 catalog, rank stars by a reproducible representative maximum apparent visual brightness rather than by a one-off exceptional historical observation. This keeps the ranking stable enough to reproduce while still respecting ordinary variability.

Variable and eruptive behavior belongs in the individual star notes. Add a standard field, **Outbursts and exceptional brightness**, whenever applicable. Use it for unusual maxima or minima, eclipses, eruptions, major dimming events, and historically noteworthy departures from the star's representative range. Examples include Betelgeuse's 2019–2020 Great Dimming, Algol's regular eclipses, Mira's unusually bright maxima, and similar exceptional behavior in other variable stars.

The ranking and the notes therefore serve different purposes: the Bright 50 ranking uses a representative maximum, while the star note preserves exceptional observations and outbursts without allowing a rare event to destabilize the catalog order.

## 2026-09-02 — Adopt second-magnitude bright-star layer

Replace the arbitrary Bright 50 cutoff with a physical inclusion rule: include every star whose representative maximum apparent visual magnitude reaches V ≤ +2.50. This should capture essentially all first- and second-magnitude stars while preserving a reproducible threshold.

This bright-star layer is observer-first rather than a replacement for the complete α/β Bayer catalog. Its purpose is to enrich the weekly Almanack with more naked-eye landmarks and more calendar dates carrying useful observing content. Each included bright star should receive its best-visibility date under the same 9 PM local apparent solar time rule used elsewhere in the project, then be available for a concise star note on that date or week.

Star notes may include color, multiplicity, navigation or cultural significance, variability, and the standard **Outbursts and exceptional brightness** field where relevant.

## 2026-09-02 — Magnitude display convention

The Almanack prose should display stellar magnitudes as whole-number visual magnitude classes rather than decimal magnitudes. Decimal precision is retained in the underlying data for calculations and star-chart rendering, where it is useful for differentiating symbol brightness.

For stable stars, display the whole-number class only, such as **V1** or **V2**. For variable stars, display the bright-to-faint class range, such as **V2–V3**, while preserving the precise decimal bright and faint V magnitudes in machine-readable catalog fields. This keeps the printed Almanack visually simple without discarding quantitative precision from the source data.

## 2026-09-02 — Completed Bayer and second-magnitude integration

The Bayer source audit and supplement are now incorporated into the generated catalog. The current audited Bayer source contains 177 rows representing 175 distinct α/β designations; this supersedes the earlier 159-row state recorded above without rewriting that historical log entry.

The second-magnitude layer is defined by representative maximum apparent Johnson V ≤ +2.50, with the Sun excluded. The pinned HYG v4.1 extraction initially produced 95 raw rows. Reconciliation removed the Sun, suppressed a duplicate Capella component, and represented Alpha Centauri as one naked-eye system with flux-combined V while retaining both component identifiers. The resulting baseline contains 92 naked-eye stellar systems: 51 already represented in the α/β Bayer layer and 41 genuinely new non-α/β systems.

The GCVS boundary audit found 81 catalog rows whose listed maximum reaches +2.50 or brighter. Of these, 43 are in the GCVS visual/photovisual/V-system bucket, 3 are explicitly photographic, and 35 use other or blank systems. Reconciliation of the 43 V-system candidates classified 27 as already represented in the HYG bright baseline, 10 as exceptional eruptive/transient maxima that do not define ordinary membership, and 6 as requiring individual source checks. The six were resolved as follows: Polaris (α UMi), Alioth (ε UMa), and γ² Velorum are included; Mira (ο Ceti), η Carinae, and V862 Scorpii are excluded from the ordinary threshold layer, with exceptional brightness retained as note material where appropriate.

Bright-star best-visibility dates use the same observer-first solar-right-ascension rule as the Bayer catalog. The dated bright-star catalog contains all 92 reconciled systems, of which 41 add new non-α/β calendar entries. A year-boundary normalization was required for Algol so its annual occurrence is placed inside ISO 2026 rather than the adjacent Gregorian-year occurrence.

The integrated expanded Almanack build now reports 53 ISO weeks, 110 Messier objects, 177 Bayer rows, and 41 new bright-star systems. CI verifies all 53 week headings, all 371 civil-date rows, and exactly one calendar entry for every one of the 41 new bright-star systems. The ISO-year boundary remains explicit: β Reticuli has best instant 2026-12-31 20:05 UTC, best civil date 2027-01-01, ISO 2026-W53-5.

This establishes the current reproducible 2026 expanded-Almanack baseline. Independent external validation may be performed later as a cross-check, but the repository catalogs, source audits, reconciliation tables, regression tests, and CI remain the primary record of how membership and dates were derived.

## 2026-09-02 — Calendar alias deduplication policy

Deduplication is a presentation rule for the generated weekly calendar, not a catalog-membership rule. The machine-readable Messier, Bayer, and second-magnitude catalogs remain complete and unchanged, and every catalog row must still pass the fixed-object placement completeness check even when a redundant display alias is suppressed.

The scope is deliberately narrow: compare generated fixed-object calendar entries with legacy best-visibility text already present in `almanack.md`. When the legacy text and a generated entry clearly identify the same physical object, retain the existing legacy entry and suppress the additional generated alias. Examples include a proper-name legacy entry such as Aldebaran or Rigel followed by the same star from the complete Bayer catalog, and a descriptive legacy Messier entry followed by the generated bare Messier designation.

Identity is established conservatively. Messier objects are matched by their M-number. Stellar aliases are matched by an explicit proper name when one is available, or by an exact Bayer designation when no proper name is available. The deduplicator does not infer identity from proximity, brightness, constellation membership, or similar-looking names.

Generated catalog rows are never deduplicated against one another. In particular, genuine separately designated components such as α¹/α² or β¹/β² remain separate, and no source row is deleted or collapsed. The deduplicator changes only what is printed in a calendar cell; provenance and catalog completeness remain in the appended catalog sections and source CSV files.

If a generated entry is suppressed because the same object is already represented by legacy calendar text, that catalog row is still recorded as successfully placed for the builder's completeness accounting. This keeps the invariant that all 110 Messier rows, all audited Bayer rows, and all new bright-star rows are accounted for while avoiding duplicate-looking observer-facing entries.

## 2026-09-02 — Cross-date Messier reconciliation

Content audit exposed a legacy Messier duplication that the first alias rule did not catch: M37 appeared once on the generated catalog best date and again as a descriptive legacy entry on the neighboring civil date. Messier identity is therefore reconciled globally across the weekly calendar by M-number, not merely within a single date cell.

For every Messier object, `messier-visibility-2026.csv` is authoritative for the calendar placement date. A legacy `Best visibility:` event carrying the same M-number on any other date is suppressed before generated fixed-object injection. If a descriptive legacy Messier label already appears on the catalog best date, that human-readable label is retained and the bare generated alias is suppressed as before.

This remains a presentation-only rule. All 110 source rows remain unchanged and must still be accounted for by the builder. CI now requires each M1 through M110 identity from the source catalog to occur exactly once in the calendar and specifically on its computed best-visibility date.

## 2026-09-02 — Observer-target deduplication

The calendar-level rule is now: **deduplicate observing targets, not stars**. Machine-readable catalog rows continue to describe the underlying stellar records and are not deleted merely because multiple rows are presented as one practical naked-eye target.

For the Bayer layer, rows with the same exact Bayer designation and the same placement date may share one observer-facing calendar target. The most informative available label is preferred. This resolves the α Comae Berenices case: the two retained source/component records remain in the appended Bayer catalog, while the weekly calendar now prints one target, **Diadem (α Com)**, rather than both `Diadem (α Com)` and `α Com`.

Separately numbered Bayer designations remain separate observing targets. Thus α¹/α² and β¹/β² are not collapsed by this rule. Likewise, physically related stars are not merged merely because they belong to the same gravitational system: a future special-mentions layer may list Proxima Centauri separately from the naked-eye Alpha Centauri A/B observing target.

This rule is presentation-only and observer-first. Every underlying Bayer row still participates in completeness accounting even when more than one row maps to the same calendar target. Future notable-object layers, including nearby stars such as Proxima Centauri and naked-eye stars with confirmed exoplanets, should remain separate from the systematic α/β and V ≤ +2.50 inclusion layers.

## 2026-09-02 — Special Mentions and observing-aid notation

Special Mentions are an editorial layer separate from the systematic Messier, α/β Bayer, and V ≤ +2.50 bright-star layers. A Special Mention earns inclusion because its historical, cultural, observational, or scientific story is worth telling. Significance selects the object; the sky selects its placement.

Special Mentions are not allocated by zodiac quota. Candidate objects receive their natural 2026 placement from the same observer-first visibility logic used by the Almanack. A zodiac month may therefore contain several Special Mentions, one, or none at all. Do not add or move objects merely to balance otherwise quiet zodiac months.

The recovered candidate nucleus includes Proxima Centauri, Barnard's Star, Wolf 359, 61 Cygni, Epsilon Eridani, Lalande 21185, Rigel, Arcturus, Deneb, R Coronae Borealis, Eta Carinae, Sirius B, 40 Eridani B, Vega, and Thuban. Antares is an additional natural candidate because its name and appearance preserve the historical “rival of Ares” story. The candidate pool may grow; there is no predetermined final count.

Each Special Mention should answer three observer-facing questions: **Why should I care? When should I look? What do I need to see it?** Scientific history and science-fiction history may both be relevant when they materially explain why an object matters to human culture.

Observing-aid notation is Almanack-wide, not restricted to Special Mentions. Stars, Messier objects, and Special Mentions should identify the minimum practical observing aid for the actual target under ordinary observing conditions:

- **👁** — Naked eye
- **B** — Binoculars
- **🔭** — Telescope

The classification is practical rather than a statement of an absolute physiological detection limit. For a multiple system, classify the actual observing task: Sirius itself is a naked-eye target, while observing Sirius B is a telescope task. Variable objects may require context when their practical visibility changes substantially with brightness.

For urban Natural Philosophers, the Almanack should explicitly recommend astronomical binoculars as a particularly useful first instrument. Binoculars recover many stars hidden by city light pollution, enrich open clusters, make a number of Messier objects approachable, provide a wide field with both eyes, and require very little setup. The **B** class is therefore a first-class observing mode, not shorthand for an inferior telescope target.

## 2026-09-04 — Urban observer equipment principle

The Almanack's observing-aid recommendation should answer **“What should a city observer take outside to enjoy this object?”**, not “Could an exceptional observer possibly detect this object without optics under favorable or dark-sky conditions?” Light pollution therefore justifies a conservative naked-eye classification, and objects that are technically naked-eye under dark skies may deliberately receive a binocular recommendation for an urban observer.

Binocular observing is a positive, first-class category and supports the Almanack's role as an advertisement for binocular astronomy. The notation remains **👁** for naked eye, **B** for binoculars, and **🔭** for telescope. Exact magnitude/equipment borders are not yet settled and must not be treated as final merely because provisional thresholds exist in implementation code. Extended objects such as galaxies and nebulae may also require classification beyond integrated magnitude alone.

## 2026-09-05 — Zodiac Days, astronomy/astrology boundary, and priority question

The Star Almanack deliberately marries astronomical and astrological sky frameworks while keeping their geometries distinct. IAU constellations are bounded regions of the celestial sphere; Messier objects therefore belong to actual constellations according to their coordinates. Zodiac signs, by contrast, are twelve equal 30° sectors of the ecliptic and do not follow IAU constellation boundaries. Almanack prose should never infer a Messier object's constellation from the zodiac sign associated with a date.

For Gemini, M35 is the Messier object within the constellation Gemini and should be identified in Sky Notes by Messier number, useful name/designation where applicable, and object type. More generally, constellation-oriented Sky Notes should identify Messier objects belonging to the astronomical constellation.

**Zodiac Day is explicitly calendrical, not a one-degree bin.** Day 1 begins with the Sun's ingress into a tropical zodiac sign. The days are counted from that ingress until the next solar ingress, when the count resets to Day 1. Zodiac Days are therefore not equivalent to Aries 1°, Aries 2°, etc., and a sign's calendrical run need not be exactly 30 civil days.

The historical-priority question remains open. Numbered zodiac degrees are ancient and are not the claimed innovation. There is at least a modern precedent for astrology publications describing numbered sign or “season” days counted from solar ingress, so the Star Almanack should not claim priority without a deeper historical search. The precise research question is: **Who first published a complete system of numbered Zodiac Days, with Day 1 beginning at solar ingress and the count continuing until the next ingress?** Research should distinguish occasional phrases such as “first day of Aries,” degree numbering, and isolated season-day counts from a systematic twelve-sign calendrical presentation.

The essay **“Get Over It”** fits this methodology: astronomy and astrology can be presented together without pretending that constellations and zodiac signs have identical boundaries or meanings. Define each system correctly, then let both describe the same sky in their appropriate roles.

## 2026-09-05 — Solar-station chain of custody

Preserve a strict chain of custody for solar ingresses, quarter days, and cross-quarter days:

**Star Almanack calculation → authoritative source data → Jekyll publication → independent external verification.**

The astronomical source of truth is the Star Almanack computational pipeline, not a published ephemeris table and not the website HTML. Solar-station times are calculated from the Sun's apparent geocentric tropical ecliptic longitude. The 12 zodiac ingresses occur at 30° intervals; the quarter points are 0°, 90°, 180°, and 270°; the cross-quarter points are 45°, 135°, 225°, and 315°. For completeness, the computational framework may solve all 24 stations at 15° intervals, while only named or editorially selected stations need be published.

`ISO2026.md` is the preserved 2026 ingress record and explicitly states that the ingress times are calculated by Star Almanack from apparent solar longitude, with published ephemerides used independently for validation only. `quarter-and-cross-quarter-days.yaml` preserves the same apparent-geocentric solar-longitude convention for the eight seasonal stations.

The September equinox provides the custody example. The Star Almanack source already contains the calculated Libra ingress / September equinox at **2026-09-23 00:05:13 UTC**. An externally rounded **00:05 UTC** value was briefly introduced into the published W39 page during editing. That value must not be treated as the source simply because it agrees. The published page was corrected to the full internally calculated **00:05:13 UTC** value from the source-of-truth record.

When several names describe the same astronomical instant, they must share one timestamp rather than repeating the same time after each alias. Example:

**September Equinox — First Point of Libra — Mabon — ♎ Libra ingress (180°) — 00:05:13 UTC**

The same presentation rule applies to the March equinox and any other coincident named event.

External authorities such as USNO, NASA, JPL Horizons, or independent published ingress tables are verification sources only. They may confirm the definition, precision, and plausibility of a Star Almanack result, but they do not overwrite or become the source of the published value. If a discrepancy appears, investigate the Almanack computation and its frame/time-scale conventions rather than silently substituting an external number.

Architectural custody remains explicit: Python owns astronomical computation and source normalization; Jekyll owns page assembly and presentation; generated HTML is output, never source of truth; provenance verification is an independent audit layer after publication.

## 2026-09-05 — Finder-chart constellation and asterism standard

The finder-chart visual system is now settled. Use the Martz 88-constellation stick-figure system as the baseline geometry for constellation figures, with appropriate credit to the Martz-Kohl Observatory and the underlying constellation-stick-figure tradition/data. Do not improvise a new constellation skeleton when a Martz baseline figure exists.

Star Almanack will define and maintain its own asterism figures as a distinct observer-facing layer. Familiar orienting patterns such as the Water Jar, Great Square, Orion's Belt, Teapot, Northern Cross, Sickle, and similar useful naked-eye figures may therefore be standardized independently of constellation figures.

Finder charts use a night-sky presentation. The visual convention is:

- **Blue** — constellation stick figure.
- **Green** — Star Almanack asterism figure.
- **Light gray, dashed** — IAU constellation boundaries.
- **White/light** — stars, labels, target arrows, and other navigation information.
- **Dark navy/black** — night-sky background.

When an asterism overlaps a constellation figure, retain the conceptual distinction by drawing the green asterism over the blue constellation figure rather than treating them as the same object. Constellation boundaries remain subordinate orientation aids and should not compete visually with the recognizable figure or highlighted asterism.

Finder-chart titles should be simple target titles such as **Sadalmelik Finder**. Target arrows should have a clearly visible shaft long enough to function as navigation rather than appearing as a stubby marker. The charts should remain reproducible, source-driven diagrams rather than generated artwork.