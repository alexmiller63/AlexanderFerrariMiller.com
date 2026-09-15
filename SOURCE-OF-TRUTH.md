# Star Almanack Source of Truth

This file documents which repository files are authoritative and which files are generated. Generated weekly pages and rendered HTML are never the source of truth.

## Stellar data

### Bayer alpha/beta layer

Authoritative catalog data:

- `expanded-bayer-stars.csv` — stellar identity, Bayer designation, proper name where available, constellation abbreviation, right ascension, declination, magnitude, and catalog identifiers.
- `expanded-bayer-visibility-2026.csv` — generated 2026 best-visibility placement for the Bayer catalog.

Builders:

- `build_bayer_catalog.py`
- `compute_bayer_visibility_2026.py`

### Bright-star layer

Authoritative catalog data:

- `bright-stars-2mag.csv` — reconciled naked-eye stellar-system catalog.
- `bright-star-visibility-2026.csv` — generated 2026 best-visibility placement. This preserves proper name, Bayer code, constellation abbreviation, right ascension, declination, decimal V magnitude, source/provenance, catalog identifiers, best date, and ISO week date.
- `bright-variable-reconciliation.csv` — authoritative variability enrichment for bright stars where the GCVS reconciliation identifies a variable star.

Builders/audits:

- `build_bright_star_catalog.py`
- `compute_bright_star_visibility_2026.py`
- `reconcile_bright_variables.py`
- `audit_gcvs_bright_boundary.py`

### Special stars

Authoritative catalog data:

- `special-star-catalog.csv`
- `special-stars.yaml` where editorial material beyond the compact catalog is required.

Generated 2026 placement:

- `special-star-visibility-2026.csv`

## Messier objects

Authoritative/generated fixed-object data are carried in the repository Messier source and `messier-visibility-2026.csv`; the latter supplies the 2026 best-visibility placement used by the expanded Almanack builder.

## Almanack integration

`build_expanded_almanack.py` combines the calendar and fixed-object catalogs into `almanack-expanded.md`.

`enrich_stellar_entries.py` is the mandatory stellar presentation pass. It reads the Bayer visibility catalog, bright-star visibility catalog, and reconciled bright-variable data and normalizes catalog-backed stellar entries so the published Almanack preserves Bayer designation, known-variable status, declination band, and observing season while applying the Almanack magnitude-display rule.

`publish_weekly_pages.py` converts the integrated and enriched Almanack into the weekly pages under `site/2026/W01/` through `site/2026/W53/`.

Therefore:

**Catalog CSV/YAML → visibility computation → `build_expanded_almanack.py` → `enrich_stellar_entries.py` → `almanack-expanded.md` → `publish_weekly_pages.py` → weekly HTML.**

The weekly HTML is output, not source.

## Required stellar display fields

Every observer-facing Almanack stellar entry SHALL display, when applicable:

- proper name;
- Bayer designation, using the Greek letter rather than the three-letter Latin code;
- constellation via the Bayer constellation abbreviation;
- variable-star magnitude as a whole number, prefixed by `V`;
- no magnitude for non-variable stars;
- declination band derived consistently from declination;
- observing season;
- best-visibility civil date and ISO week placement.

The authoritative catalog magnitude remains decimal. Presentation precision depends on output:

- **Almanack calendar text:** whole-number magnitude for variable stars only.
- **Charts:** magnitude to 1 decimal place.

The compact canonical Almanack form is:

`Proper name (Bayer) — V whole-number-magnitude [when variable] — Declination-band Season`

Declination Band is derived from declination using the tropical boundaries:

- declination > +23.44°: Northern;
- −23.44° through +23.44°: Tropical;
- declination < −23.44°: Southern.

Season is derived from the best-visibility civil date using Winter, Spring, Summer, and Autumn.

Declination Band SHALL precede Season in observer-facing stellar entries.

## Example: Enif

The authoritative bright-star visibility row for Enif identifies:

- Bayer code: `Eps` → `ε`;
- constellation: `Peg` (Pegasus);
- declination: approximately `+9.875°`;
- decimal V magnitude: `2.38`;
- best date: `2026-10-05` (`2026-W41-1`).

The variable-star reconciliation identifies `eps Peg` as variable. Therefore:

- Almanack: `Enif (ε Peg) — V 2 — Tropical Autumn`
- Chart magnitude: `2.4`

Here `Tropical` is the Declination Band and `Autumn` is the Season.

## Maintenance rule

When a stellar entry is wrong or incomplete, correct the appropriate catalog, visibility computation, or enrichment source and regenerate. Do not hand-patch a single weekly HTML page except while diagnosing a rendering problem.
