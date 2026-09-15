# Star Almanack Database Inventory and Migration Map

## 2026-09-15 — Initial non-destructive inventory

Status: inventory only. **No generator or source-data migration is performed by this document.**

The repository already behaves partly like a database, but identity is distributed among several files and several catalog-specific schemas. The migration should first unify physical identity while preserving catalog-entry and observing-target structure.

## Current authoritative and high-value source data

### `fixed-objects.yaml`

Current code explicitly describes `Historical/fixed-objects.yaml` as the authoritative fixed-object catalog. It contains separate schemas/collections for at least:

- `messier`: `id`, `ngc`, `name`, `type`, `con`, `ra_h`, `dec_deg`, `mag`, `size_arcmin`, `best`, `iso`;
- `bayer`: `bayer`, `con`, `name`, `ra_h`, `dec_deg`, `mag`, `best`, `iso`;
- `special`: `id`, `name`, `catalog`, `con`, `ra_h`, `dec_deg`, `mag`, `best`, `iso`, `note`;
- `component`: Bayer/constellation/component/name/position/magnitude data;
- shared object type codes.

This file currently mixes physical identity, catalog identifiers, display names, coordinates, observing properties, calendar-derived fields, and editorial facts. It is therefore the primary migration source but should eventually map into several logical relations rather than one monolithic table.

Important identity issue: the same physical star or deep-sky object may qualify through more than one current collection or catalog. Collection membership must not imply a new `fixed_object_id`.

Important target issue: one source row does not necessarily mean one physical object. Some rows represent composite observing targets, multiple systems, asterisms, or extended sky regions.

### `fixed-object-regions.yaml`

Derived companion data for fixed-object region membership, including Milky Way membership/regions. This should remain **derived relationship data**, keyed in the future by `fixed_object_id`, rather than becoming an independent identity source.

### `caldwell-catalog.csv`

Caldwell catalog source data exists independently of `fixed-objects.yaml`. Rows include Caldwell designation, NGC designation, constellation, type, coordinates, magnitude, size, common-name field, and source/provenance. Simple entries can map to one physical object, but composite entries require a `catalog_entry` plus typed target relationships.

### Finest NGC data and overlap tables

The repository has a Finest NGC population path and explicit overlap data such as `finest-ngc-caldwell-overlap.csv`. The existence of an overlap table is direct evidence that catalog identity is already a many-to-one problem. Under the database model, simple Finest NGC and Caldwell entries resolve to shared physical identities; overlap should become derivable from shared target/object relationships rather than remain the long-term identity mechanism.

### `asterism-member-coordinates.csv` and `asterism-catalog-overlap.csv`

The asterism population generator consumes member coordinates and catalog-overlap data. These map to `asterisms`, `asterism_memberships`, and cross-identifiers to fixed objects. Asterism membership is a relationship, not a duplicate fixed-object record.

### Messier editorial/common-name data

The repository contains `messier-editorial.json`, `messier-common-names-nasa.yaml`, and common-name reconciliation tooling. These contain valuable editorial and provenance information that should migrate into object facts, identifiers/display metadata, and sources rather than be discarded.

### Bayer/bright-star visibility and enrichment data

Existing stellar enrichment tooling consumes Bayer, bright-star, Messier, and fixed-object data. Bayer designation must become an `object_identifier` attached to the physical star. α/β status is derivable from Bayer designation and is an enrichment trigger, not a separate identity.

### Sky Notes

Existing Sky Notes are descriptor-first and consume fixed-object data. Sky Notes should ultimately query/assemble database facts and relationships by `fixed_object_id` or structured observing target. Generated prose remains presentation and must not become the only canonical store of a fact.

### Generated visibility/calendar files

Files such as generated Messier/Caldwell visibility CSVs and yearly Almanack products are derived outputs. They should not receive permanent object identities independently. Future generators should carry physical-object and/or observing-target identity through their intermediate records so outputs remain traceable to canonical data.

## Initial logical migration map

| Current concept | Database destination | Migration treatment |
| --- | --- | --- |
| Simple Messier row | `catalog_entries` + one `catalog_entry_targets` relationship + `fixed_objects` + `object_identifiers` | Resolve one physical object; attach M/NGC/IC identifiers |
| Composite/region Messier row | `catalog_entries` + typed `catalog_entry_targets` | Preserve observing-target semantics; do not invent one physical object |
| Bayer row | `fixed_objects` + `object_identifiers` | Resolve star; Bayer is identifier, α/β is derived trigger |
| Special-star row | existing `fixed_object_id` + membership + `object_facts` | Merge with same star when already known; migrate `note` as fact(s) |
| Component row | fixed object/component relationship | Determine whether component is separately observable physical object; never infer identity solely from display label |
| Simple Caldwell row | `catalog_entries` + one target relationship + existing/new `fixed_object_id` | Prefer NGC/IC cross-ID for deterministic reconciliation |
| Composite Caldwell row | `catalog_entries` + multiple/typed `catalog_entry_targets` | Preserve multi-object, complex, asterism, or region semantics |
| Finest NGC row | `catalog_entries` + target relationship + existing/new `fixed_object_id` | Reconcile through NGC/IC identity; overlap becomes derivable |
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

Before identity reconciliation, classify each catalog row as one of: `single_object`, `multiple_objects`, `structured_system`, `asterism`, `region`, or `complex` when the source semantics require it. Only `single_object` rows participate directly in one-row/one-`fixed_object_id` reconciliation.

## Permanent ID assignment

Do **not** assign IDs according to calendar date, current file order, Messier number, Bayer letter, or popularity. Those are mutable or domain-specific orderings.

For the initial migration, first produce a reconciled physical-object set with composite/region/asterism catalog targets separated from physical identity. Sort that reconciled set by a documented deterministic migration ordering solely to make the first assignment reproducible, then assign sequential positive integers. Once committed, those integers become permanent and the sorting rule is never used to renumber existing objects. New physical objects receive the next unused integer.

The exact deterministic initial sort should be chosen only after the reconciliation audit shows which stable external identifiers are available across all object classes.

## Resolved exception cases from the identity audit

The compact exception audit confirms 8 cases lacking ordinary cross-source physical identifiers. They are schema cases, not unidentified records:

- **M24 — Sagittarius Star Cloud**: Milky Way/star-cloud region target.
- **M40 — Winnecke 4**: double-star observing target; preserve stellar component identities separately.
- **M45 — Pleiades**: physical open cluster with associated asterism/member relationships.
- **C14 — Double Cluster**: one Caldwell entry targeting NGC 869 and NGC 884.
- **C33 — Eastern Veil Nebula**: one Caldwell entry encompassing NGC 6992 and NGC 6995.
- **C41 — Hyades**: physical cluster with a corresponding asterism relationship.
- **C49 — Rosette Nebula**: complex target spanning multiple NGC designations.
- **C99 — Coalsack Nebula**: extended dark-nebula region.

These require a catalog-target relationship layer before permanent IDs are assigned.

## Known duplication/normalization pressure points

- Messier objects commonly also have NGC/IC identities.
- Caldwell and Finest NGC explicitly overlap.
- A deep-sky object can occur in Messier, Caldwell/Finest-related data, asterism relationships, and generated calendars without becoming multiple objects.
- A star can be simultaneously Bayer α/β, bright, special, named, an asterism member, and a component/multiple-system participant.
- Proper/common names are presentation labels and can be null, multiple, disputed, or changed.
- Catalog rows can be composite targets and must not be flattened into fake physical identities.
- M24 is represented as a Milky Way/star-cloud target rather than a conventional compact catalog object, so object-class semantics must be preserved during normalization.
- M40 is a double-star observing target; component identity must not be flattened accidentally.

## Provenance migration

Source strings and provenance files already present in the repository should be retained. Migration should distinguish:

- imported catalog facts;
- curated Almanack editorial facts;
- derived calculations;
- external historical/lore research;
- generated presentation.

Every new lore/history enrichment record should be attachable to one `fixed_object_id` or, where the statement concerns a composite/region target itself, to the appropriate catalog/observing target with one or more source records.

## Generator migration boundary

No existing generator changes yet. The safe sequence is:

1. complete inventory;
2. classify catalog entries by target semantics;
3. reconcile physical identities;
4. create the permanent ID registry;
5. validate that aliases/catalog target relationships reproduce existing overlap behavior;
6. add normalized database-style source files alongside existing files;
7. teach consumers to read the normalized data incrementally;
8. compare generated output against current regressions;
9. retire redundant identity mechanisms only after equivalence is demonstrated.

## Next audit

Create the machine-readable catalog-entry/target layer for the resolved exception cases first. Then rerun physical-object reconciliation with those rows excluded from naive one-row/one-object identity assignment. The resulting reconciled physical-object set becomes the input to deterministic initial `fixed_object_id` assignment.
