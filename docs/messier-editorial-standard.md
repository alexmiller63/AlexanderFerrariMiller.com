# Messier Editorial Standard

Adopted 2026-09-08 for the Star Almanack calendar.

## Reader-facing form

Every Messier object in the calendar uses a reader-facing astronomical description:

- Named object: **[Common name] (M#), [editorial type] in [constellation]**
- Object without an accepted common name: **Messier # (M#), [editorial type] in [constellation]**

Examples:

- **Orion Nebula (M42), emission nebula in Orion**
- **Trifid Nebula (M20), emission and reflection nebula in Sagittarius**
- **Messier 15 (M15), globular cluster in Pegasus**

The object type should be the most useful scientifically accurate classification for a general astronomy reader. A broad catalog class may therefore be refined editorially. For example, a catalog may group M42 under a broad diffuse-nebula class, while the Almanack reader-facing type is **emission nebula**.

## Data owns the astronomy; Python owns the formatting

Astronomical editorial judgments must be stored explicitly in source data. Python must not contain object-specific exceptions for names, object types, or other astronomical classifications.

Each Messier source record should carry, at minimum:

- Messier designation
- accepted common name, when applicable
- underlying catalog classification
- reader-facing editorial type
- constellation
- provenance for the editorial classification

The formatter reads those fields and renders the standard calendar wording. It does not decide whether an individual object is an emission nebula, reflection nebula, globular cluster, spiral galaxy, or another astronomical type.

## Provenance

All 110 Messier editorial classifications should be auditable. The source data should record authoritative provenance for each reader-facing classification rather than documenting provenance only for ambiguous objects.

Prefer authoritative astronomical sources such as NASA mission/science material, professional observatory or catalog documentation, SIMBAD/CDS, or another primary or standard astronomical source appropriate to the classification.

Provenance supports the editorial decision; it is not intended to clutter the calendar display. The calendar presents the concise reader-facing wording while the source record preserves why that wording was chosen and where the classification came from.

## Compound nebulae

Where a Messier object genuinely combines important nebular phenomena, the editorial type may state more than one. The Trifid Nebula is the model case: its reader-facing type is **emission and reflection nebula**. Its prominent dark lanes remain an important structural feature but do not need to make the calendar classification cumbersome.

## Architectural rule

The authoritative chain is:

**catalog identity/data → curated editorial classification → authoritative provenance → generic formatter → calendar wording**

Generated HTML is never the source of an astronomical editorial decision.
