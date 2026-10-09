# Researched story completion

Story files are owned by permanent fixed-object ID: `stories/<collection>/<fixed_object_id>.md`.
An existing story without a status is **pending**, as is every generated baseline.
One verified complete story satisfies the object across collections and future weeks.
Overlapping catalog designations do not require separate stories for the same object.

After reviewing the research and checking the published story and finder links, add:

```yaml
---
fixed_object_id: 698
status: complete
research_checked: true
finder_checked: true
publication_checked: true
artwork: stellar-finder
---
```

Use the actual object ID. Keep `artwork` only when applicable. The three checked
fields record reviewer attestations: claims were checked against the recorded
sources, finder/story links were tested, and the published account was verified.
The loader requires a hed, dek, body and a recorded source URL for complete stories.
It rejects invalid statuses and incomplete completion records. It does not perform
or infer research review or live publication checks from the presence of a file.

Use `status: pending` while writing or when a correction invalidates the previous
review. Weekly observing conditions remain separate from the permanent story.

Sky Notes builds save completion counts and the pending object list in their
generated source JSON and print the pending list in the action log. For a read-only
report without rebuilding:

```sh
python tools/story_completion.py 2025-12-29 2026-01-04
```

Catalog targets without a permanent ID remain visible in the pending list; they
cannot become complete until their story is associated with a permanent identity.
