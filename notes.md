# Star Almanack Notes

Continuous project log. Append new entries; do not rewrite prior entries except to correct a documented factual error.

## 2026-09-16 — Fixed-object story layer specification

Narrative content for fixed objects is a separate content layer and does not belong in `database/`. Structured machine data remains in `database/`; human-readable narrative lives under the top-level `stories/` directory.

Story collections currently include `alpha-stars/`, `beta-stars/`, `special-stars/`, `messier/`, `caldwell/`, and `finest/`. Story filenames are based only on the permanent `fixed_object_id`, for example `stories/alpha-stars/123.md`. Object names, Bayer designations, Messier numbers, Caldwell numbers, and other mutable labels must not be used as inter-layer keys or filenames.

The permanent `fixed_object_id` is passed as a parameter. The consumer derives the story path deterministically from collection plus key, such as `stories/alpha-stars/{fixed_object_id}.md`. Therefore the database does not store narrative prose or redundant story filenames.

One physical fixed object may legitimately have zero, one, or multiple stories when it participates in multiple collections. The permanent object identity remains singular; the stories describe the object's different catalog, historical, observational, or editorial contexts.

Architecture rule: `database/` = facts, identities, and relationships; `stories/` = human-readable narrative; `fixed_object_id` = the bridge between them.
