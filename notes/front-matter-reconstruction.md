# Front-matter reconstruction record

Reconstructed 2026-10-22 at Alexander Ferrari Miller’s request. This is an editorial recovery record, not a claim that a finished front-matter manuscript was found intact.

## Result and editorial boundaries

`front-matter.md` now assembles a navigable front-matter draft. Existing long-form manuscripts remain separate authoritative sources and are linked in full. Their words have not been rewritten for this reconstruction. The earlier approved correction to `rabbis.md` — “beneath the same stars far from home” — is retained.

The new arrangement is editorial, not a recovered final order. The three-story grouping is supported by `3-stories-baseline.md`; the placement of the later essays and reference chapters is provisional. The text explicitly distinguishes reconstructed explanatory prose from surviving manuscripts.

No archived folder is used as an active source or build dependency. Current source files and the current constellation generator control the reconstructed conventions. A prior commit is cited below only as evidence of an earlier editorial decision.

## Source inventory

All paths below are relative to the active repository root.

| Recovered part | Source | Recovery status |
|---|---|---|
| Opening meditation | `signs-and-seasons.md` | Full surviving manuscript, linked unchanged |
| Reader’s guide | `how-to-use.md` | Full surviving manuscript; contains older feature descriptions requiring comparison with current edition |
| Original three-story group | `3-stories-baseline.md` | Surviving synopsis baseline establishes Rabbis, Tyson, and Libra as the original core; full manuscripts take precedence over synopses |
| Two Rabbis | `rabbis.md` | Full surviving manuscript, including the approved same-stars correction |
| Imagined Tyson argument | `tyson.md` | Full surviving manuscript; must remain labeled imagined |
| Libra birthday | `birthday-libra.md` | Full surviving manuscript |
| Grandmother’s birth century | `grandmother.md` | Full surviving manuscript; unanswered historical questions preserved |
| Ordinary day | `most-ordinary.md` | Full surviving manuscript; final placement not recovered |
| Zodiac and planetary symbol key | `typography.md`, “General Symbol Rule,” “Zodiac Symbols,” “Planetary Symbols,” and “Symbol Key” | Key assembled from recorded symbols and first-use convention; typography explicitly assigns key to front matter |
| Lunar phase symbols | `how-to-use.md`, “Read the Moon” | Four phase symbols and labels recovered |
| Equipment key and urban baseline | `notes/observing-equipment.md` | Labels and baseline recovered; note leaves exact equipment thresholds unsettled |
| Mensa, Microscopium, Serpens | `tools/populate_constellations.py`, especially `FRONT_MATTER`, `SERPENS_COMPONENTS`, and `constellation_magnitude()` | Explanation newly reconstructed from current explicit exception rules; no claim of verbatim recovery |
| Constellation and asterism chart conventions | `notes/constellations-and-asterisms.md` | Blue/green/white convention, no displayed asterism boundary, spherical-centroid explanation recovered |
| Diagram-versus-photograph explanation | `render_observer_views.py`, module documentation | Renderer explicitly recommends explanation in legend/front matter; reconstructed short reader-facing note |
| Reader-facing mathematics | `mathematics.md` | Full surviving chapter, linked with equation rendering |
| Technical mathematics | `math.md` | Separate technical reference; not replaced with the older `map.md` |
| Moon names | `moon-names.md` | Full surviving text; final front/back-matter placement not recovered |
| Keplerian study aid | `EPHEMERIS-PROVENANCE.md` | Explicit front-matter assignment recovered; complete explanatory manuscript not found |

## Dated evidence and superseded proposals

The typography discussion from August 16 specified a front-matter symbol key and a first-use naming convention. Those requirements survive in the current `typography.md` and are independently repeated in `how-to-use.md`.

The September 9 commit [Document Mensa and Microscopium stick-figure rule](https://github.com/alexmiller63/AlexanderFerrariMiller.com/commit/4fba7638699fcd026d53c5a51e1101c0012c7731) explicitly records a front-matter explanation, initially titled “What’s with Mensa and Microscopium?” Earlier conversation records subsequently expand the title to “What’s up with Mensa, Microscopium, and Serpens?” The complete final prose was not located. The reconstruction uses the expanded heading and checks its rules against the current generator.

Earlier discussion briefly proposed Telescopium and Norma as exceptions. The later accepted correction gives them their actual source-defined figures. Only Mensa and Microscopium use the current α/β mean fallback; Serpens uses separate Caput/Cauda figure members. This is verified directly in the current generator rather than inferred from the earlier proposal.

The distinction between 88 constellations, 86 constellations with figures, and 87 individual figures is intentional: Serpens contributes two figures, while Mensa and Microscopium contribute none.

## Gaps and unresolved placement

1. No final combined table of contents or finished single front-matter manuscript has been located. Absence from the searches is not proof that no further copy exists.
2. The front-matter assignment for Keplerian ephemera survives, but this reconstruction does not substitute implementation code for a missing educational chapter.
3. Earlier book descriptions mention astronomical symbols and pronunciation (IPA). No complete pronunciation manuscript was found in the current repository search. This is a recovery lead, not a finished chapter.
4. The recovered symbol key originally reproduced the typography source, which omitted Ceres. On 2026-10-22 Alexander identified that omission. Ceres (⚳) was added to both the front-matter key and the typography source between Mars and Jupiter; Earth is explicitly identified as a reference symbol rather than a geocentric observing target. A complete inventory of other glyphs in the current edition remains open.
5. The reader’s guide and typography manuscript describe an earlier seven-body weekly wheel and earlier presentation choices. Original prose is preserved; a separate editorial pass must reconcile these descriptions with the present edition.
6. Moon Names and technical mathematics may ultimately belong in reference chapters or appendices rather than front matter. The reconstruction links them without inventing a final placement.
7. No dedication, acknowledgments, foreword, or additional personal family history has been invented.

## Publication and maintenance

`tools/build_almanack_reading.py` generates `star-almanack/front-matter.html` from `front-matter.md` alongside the existing manuscript wrappers. Front Matter is linked from the Almanack home page, navigation, and reading index. Future editorial additions belong in the Markdown source and this recovery record; generated HTML is rebuilt from source.
