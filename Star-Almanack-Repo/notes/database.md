# Star Almanack Notes — Database

## 2026-09-15 — Treat Almanack data as a database

The Star Almanack has reached the point where its data should be treated as a database rather than as independent documents. YAML and JSON may continue to be the physical storage format during migration, but they should represent a coherent logical data model with stable identities, relationships, provenance, and integrity rules.

The database model is the source of astronomical knowledge. Generators consume it; generators must not become independent stores of astronomical facts.

### Identity

Every physical fixed object has one immutable internal surrogate key:

`fixed_object_id`

Use a sequential integer. The key has no astronomical meaning and never changes because a name, catalog designation, classification, or preferred display label changes.

Canonical rule: **one physical object = one fixed-object record = one permanent `fixed_object_id`.**

Human identifiers are attributes and aliases, not primary keys. Examples include proper names, Bayer and Flamsteed designations, HIP/HD/HR identifiers, Messier numbers, Caldwell numbers, NGC/IC identifiers, and other catalog designations.

A catalog entry or observing target is **not automatically a physical object**. Some catalog entries designate one physical object; others designate multiple physical objects, a structured system, an asterism, a complex, or an extended sky region. Therefore permanent `fixed_object_id` values belong only to physical objects.

### Core logical entities

**fixed_objects** — one row per physical astronomical object. Holds the immutable ID and core object classification/coordinates needed to identify the physical target.

**object_identifiers** — aliases and external catalog identifiers attached to `fixed_object_id`. Each identifier records its namespace/catalog and value. Preferred display names are presentation metadata, not identity.

**catalog_entries** — one row per entry in a curated catalog or observing list, such as M24, C14, C33, C49, or a Finest NGC entry. A catalog entry has its own designation and provenance but does not necessarily receive a `fixed_object_id`.

**catalog_entry_targets** — typed relationships from a `catalog_entry` to what it designates. A target can resolve to one physical fixed object, multiple physical fixed objects, a region, an asterism, or a structured/composite target. Relationship semantics may include `designates`, `contains`, `comprises`, `has_component`, `represents_region`, or another documented type.

**catalog_memberships** — relationships expressing that a physical object or structured target participates in a curated list. For simple one-object entries this can be derived from `catalog_entry_targets`; it must not be used to force composite entries into one-object identity.

**object_facts** — structured noteworthy facts about a fixed object. Facts may describe physical astronomy, observing significance, history, discovery, navigation, naming, culture/lore, exceptional events, or other reasons the object matters to an observer.

**sources** — provenance records for external or internal authoritative sources.

**fact_sources** — many-to-many relationship between facts and sources. A fact should be traceable to its evidence; multiple sources may support one fact and one source may support many facts.

**constellations** — official IAU constellation entities and their authoritative boundary geometry.

**asterisms** — curated star patterns. Asterisms have member stars and drawable stick-figure relationships but no official or displayed boundary. Any geometry derived solely for centroid calculation is internal computational geometry.

**asterism_memberships** — relationships between fixed stars and asterisms, including any ordering or connectivity information required to draw the figure.

**object_constellation_membership** — geometric relationship between a fixed object's position and the official IAU constellation boundary containing it. This relationship should be derivable rather than independently hand-maintained whenever possible.

**milky_way_regions** — named Milky Way regions and the data/geometry needed to identify and render them. These remain distinct from constellations and asterisms.

### Catalog-target semantics discovered by the identity audit

The pre-migration identity audit established that the model must support catalog targets that are not ordinary one-row/one-object identities:

- **M24** — Sagittarius Star Cloud: Milky Way/star-cloud region target.
- **M40** — Winnecke 4: double-star observing target whose stellar components must remain separately identifiable.
- **M45** — Pleiades: physical open cluster with an associated visual asterism/member pattern.
- **C14** — Double Cluster: one Caldwell entry designating NGC 869 and NGC 884.
- **C33** — Eastern Veil Nebula: one Caldwell entry encompassing NGC 6992 and NGC 6995.
- **C41** — Hyades: physical cluster with a corresponding asterism/member relationship.
- **C49** — Rosette Nebula: complex target spanning multiple NGC designations.
- **C99** — Coalsack Nebula: extended dark-nebula region.

These are resolved schema cases, not missing identities. They demonstrate why a catalog row must not be equated mechanically with a `fixed_object` row.

### Star and object enrichment triggers

Research queues are derived from database relationships rather than maintained as disconnected lists. Initial high-value triggers include:

1. special-star membership;
2. α-star status;
3. β-star status;
4. Messier membership;
5. Caldwell membership;
6. Finest NGC membership.

An object qualifying through several triggers is researched once and receives one merged set of facts.

### Lore, history, and factoids

The fact layer answers the editorial question: **Why is this fixed object worth knowing, remembering, observing, or using when learning the sky?**

Physical facts and lore/history must remain distinguishable in structured data. Suitable fact categories include physical, observational, historical, discovery, naming, navigation, scientific-history, cultural/lore, star-hopping, catalog-history, and exceptional-event.

Thuban is a model case: its identity remains one fixed object regardless of its proper name, Bayer designation, or external catalog numbers, while the historical fact that axial precession made it an ancient northern pole star is attached to that same object record with provenance.

### Relationships, not duplication

A Messier object that is also Caldwell-listed or otherwise specially selected remains one physical object. A star that is α, belongs to several asterisms, has a proper name, and appears in a special-star list remains one physical object. Relationships enrich the object; they do not create copies.

Conversely, one catalog entry can legitimately relate to multiple physical objects or to a region/asterism. The database must preserve that structure instead of manufacturing a fake single physical identity for the catalog entry.

Generated Sky Notes should assemble relevant facts and relationships for a `fixed_object_id` or structured observing target. The generated prose is presentation, not the canonical database record.

### Provenance

Imported or researched facts must retain enough provenance to answer where the information came from and, where relevant, which version/date was consulted. Existing curated Almanack facts are legitimate inputs and should be migrated with their provenance when known rather than discarded and rediscovered.

Unverified lore should not silently become fact. Traditional or cultural material should be represented as attributed tradition/history, not as physical astronomy.

### Migration rules

1. Do not destroy or rewrite working source data merely to normalize it.
2. Inventory existing YAML/JSON and identify the physical entities and relationships already encoded.
3. Establish deterministic mappings from existing records to permanent IDs.
4. Detect aliases and duplicate representations before assigning separate IDs.
5. Never assign a `fixed_object_id` to a catalog entry merely because it occupies one source row; resolve whether the entry designates one object, multiple objects, a system, an asterism, or a region.
6. Preserve existing fields and provenance during migration.
7. Add database-style validation: unique IDs, unique catalog identifiers where appropriate, valid foreign keys, and no dangling relationships.
8. Move generators toward consuming normalized data incrementally; do not require a flag-day rewrite.
9. Once a permanent ID has been assigned to a physical object, never recycle or renumber it.
10. Derived data should be reproducible from canonical data wherever practical and should be marked as derived rather than hand-maintained.
11. Human-readable YAML/JSON may remain the repository storage mechanism until a different physical database engine provides a demonstrated advantage.

### Immediate next step

Define the machine-readable `catalog_entries` / `catalog_entry_targets` relationship layer for the resolved exception cases, then rerun identity reconciliation using that distinction. Only after the physical-object set is cleanly separated from composite/region/asterism targets should the deterministic initial `fixed_object_id` registry be created.
