# Star Almanack Database Inventory and Migration Map

## 2026-09-15 — Initial non-destructive inventory

Status: inventory only. **No generator or source-data migration is performed by this document.**

The repository already behaves partly like a database, but identity is distributed among several files and several catalog-specific schemas. The migration should first unify identity while preserving every existing source and generated product.

## Current authoritative and high-value source data

### `fixed-objects.yaml`

Current code explicitly describes `Star-Almanack-Repo/fixed-objects.yaml` as the authoritative fixed-object catalog. It contains separate schemas/collections for at least:

- `messier`: `id`, `ngc`, `name`, `type`, `con`, `ra_h`, `dec_deg`, `mag`, `size_arcmin`, `best`, `iso`;
- `bayer`: `bayer`, `con`, `name`, `ra_h`, `dec_deg`, `mag`, `best`, `iso`;
- `special`: `id`, `name`, `catalog`, `con`, `ra_h`, `dec_deg`, `mag`, `best`, `iso`, `note`;
- `component`: Bayer/constellation/component/name/position/magnitude data;
- shared object type codes.

This file currently mixes physical identity, catalog identifiers, display names, coordinates, observing properties, calendar-derived fields, and editorial facts. It is therefore the primary migration source but should eventually map into several logical relations rather than one monolithic table.

Important identity issue: the same physical star or deep-sky object may qualify through more than one current collection or catalog. Collection membership must not imply a new `fixed_object_id`.

### `fixed-object-regions.yaml`

Derived companion data for fixed-object region membership, including Milky Way membership/regions. This should remain **derived relationship data**, keyed in the future by `fixed_object_id`, rather than becoming an independent identity source.

### `caldwell-catalog.csv`

Caldwell catalog source data exists independently of `fixed-objects.yaml`. Rows include Caldwell designation, NGC designation, constellation, type, coordinates, magnitude, size, common-name field, and source/provenance. This maps primarily to `object_identifiers`, `catalog_memberships`, object observational attributes, and `sources`.

### Finest NGC data and overlap tables

The repository has a Finest NGC population path and explicit overlap data such as `finest-ngc-caldwell-overlap.csv`. The existence of an overlap table is direct evidence that catalog identity is already a many-to-one problem. Under the database model, Finest NGC and Caldwell become memberships/identifiers attached to one physical object; the overlap should become derivable from shared identity rather than remain the long-term identity mechanism.

### `asterism-member-coordinates.csv` and `asterism-catalog-overlap.csv`

The asterism population generator consumes member coordinates and catalog-overlap data. These map to `asterisms`, `asterism_memberships`, and cross-identifiers to fixed objects. Asterism membership is a relationship, not a duplicate fixed-object record.

### Messier editorial/common-name data

The repository contains `messier-editorial.json`, `messier-common-names-nasa.yaml`, and common-name reconciliation tooling. These contain valuable editorial and provenance information that should migrate into object facts, identifiers/display metadata, and sources rather than be discarded.

### Bayer/bright-star visibility and enrichment data

Existing stellar enrichment tooling consumes Bayer, bright-star, Messier, and fixed-object data. Bayer designation must become an `object_identifier` attached to the physical star. α/β status is derivable from Bayer designation and is an enrichment trigger, not a separate identity.

### Sky Notes

Existing Sky Notes are descriptor-first and consume fixed-object data. Sky Notes should ultimately query/assemble database facts and relationships by `fixed_object_id`. Generated prose remains presentation and must not become the only canonical store of a fact.

### Generated visibility/calendar files

Files such as generated Messier/Caldwell visibility CSVs and yearly Almanack products are derived outputs. They should not receive permanent object identities independently. Future generators should carry `fixed_object_id` through their intermediate records so outputs can always be traced back to the physical object.

## Initial logical migration map

| Current concept | Database destination | Migration treatment |
| --- | --- | --- |
| Messier row | `fixed_objects` + `object_identifiers` + `catalog_memberships` | Resolve physical object; assign one ID; attach M/NGC/IC identifiers |
| Bayer row | `fixed_objects` + `object_identifiers` | Resolve star; Bayer is identifier, α/β is derived trigger |
| Special-star row | existing `fixed_object_id` + `catalog_memberships` + `object_facts` | Merge with same star when already known; migrate `note` as fact(s) |
| Component row | fixed object/component relationship | Determine whether component is separately observable physical object; never infer identity solely from display label |
| Caldwell row | existing/new `fixed_object_id` + identifiers/membership | Prefer NGC/IC cross-ID for deterministic reconciliation |
| Finest NGC row | existing/new `fixed_object_id` + identifiers/membership | Reconcile through NGC/IC identity; overlap becomes derivable |
| Common name | `object_identifiers` or display-name metadata | Never use as primary key |
| Coordinates | `fixed_objects`/astrometric data | Used as validation aid, not sole identity when catalog cross-ID exists |
| Magnitude/size/type | object physical/observational attributes | Preserve provenance and semantics |
| `best` / `iso` | derived calendar/visibility data | Recompute from canonical astronomy where possible |
| Special `note` | `object_facts` + `fact_sources` | Preserve existing curated wording/provenance; classify fact type |
| Asterism member | `asterism_memberships` | Link member `fixed_object_id` to asterism |
| Constellation | derived official-boundary membership | Calculate from coordinates/boundary where practical |
| Milky Way region membership | derived region relationship | Calculate from authoritative Milky Way geometry/data |
| Sky Note prose | generated presentation | Build from facts/relationships; not canonical identity/fact storage |

## Identity reconciliation order

Initial migration should resolve identity using the strongest available evidence in this order:

1. explicit external catalog cross-identifiers that unambiguously denote the same physical object (for example NGC/IC, HIP/HD/HR where present);
2. existing explicit repository overlap/reconciliation records;
3. Bayer + constellation for stellar identities where unambiguous;
4. coordinates and object type as a validation/candidate-matching aid;
5. proper/common name only as supporting evidence, never as the sole database key when a stronger identifier exists.

Coordinate proximity must not silently merge distinct components, close doubles, nebula/cluster combinations, or catalog entries that intentionally represent different observing targets.

## Permanent ID assignment

Do **not** assign IDs according to calendar date, current file order, Messier number, Bayer letter, or popularity. Those are mutable or domain-specific orderings.

For the initial migration, first produce a reconciled physical-object set. Sort that reconciled set by a documented deterministic migration ordering solely to make the first assignment reproducible, then assign sequential positive integers. Once committed, those integers become permanent and the sorting rule is never used to renumber existing objects. New physical objects receive the next unused integer.

The exact deterministic initial sort should be chosen only after the reconciliation audit shows which stable external identifiers are available across all object classes.

## Known duplication/normalization pressure points

- Messier objects commonly also have NGC/IC identities.
- Caldwell and Finest NGC explicitly overlap.
- A deep-sky object can occur in Messier, Caldwell/Finest-related data, asterism relationships, and generated calendars without becoming multiple objects.
- A star can be simultaneously Bayer α/β, bright, special, named, an asterism member, and a component/multiple-system participant.
- Proper/common names are presentation labels and can be null, multiple, disputed, or changed.
- M24 is represented as a Milky Way/star-cloud target rather than a conventional compact catalog object, so object-class semantics must be preserved during normalization.
- M40 is a double-star observing target; component identity must not be flattened accidentally.

## Provenance migration

Source strings and provenance files already present in the repository should be retained. Migration should distinguish:

- imported catalog facts;
- curated Almanack editorial facts;
- derived calculations;
- external historical/lore research;
- generated presentation.

Every new lore/history enrichment record should be attachable to one `fixed_object_id` and one or more source records.

## Generator migration boundary

No existing generator changes yet. The safe sequence is:

1. complete inventory;
2. reconcile physical identities;
3. create the permanent ID registry;
4. validate that aliases/catalog memberships reproduce existing overlap behavior;
5. add normalized database-style source files alongside existing files;
6. teach consumers to read the normalized data incrementally;
7. compare generated output against current regressions;
8. retire redundant identity mechanisms only after equivalence is demonstrated.

## Next audit

The next concrete task is to enumerate the candidate physical objects across `fixed-objects.yaml`, Caldwell, Finest NGC, asterism memberships, and relevant stellar catalogs; calculate overlaps; flag ambiguous identities/components; and determine the stable external identifiers available for the deterministic initial `fixed_object_id` assignment. This audit should produce machine-readable results before any source catalog is rewritten.
