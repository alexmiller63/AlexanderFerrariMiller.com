# Story source presentation cleanup — October 27, 2026

Scope: both the 88 constellation articles and the main object-story collection.
The current inventory contains 544 distinct saved object identities: 56 curated
manuscripts, 482 Luna manuscripts, and six additional identities present only in
older JSON drafts. Alternate versions exist; they are not additional objects.

Checked 1,084 editable manuscript representations: 88 constellation Markdown,
56 curated object Markdown, 482 Luna Markdown, and 458 older JSON drafts.
All 88 constellation articles already had bottom Sources sections and needed no
substantive prose changes. The shared editorial guidance now covers both groups.

Routine SIMBAD names have been removed from narrative prose and retained in
references. Inline citations are gathered at the bottom. Source annotations,
measured values, uncertainty spellings, identity metadata and review flags are
preserved. Research snapshots, paid-stage responses and approval records were
not edited. The generator prompts now carry the shared editorial rule.

The fixed-object and inline story renderers now render source headings, lists,
Markdown links and bare source URLs as HTML. Raw HTML is escaped. Regenerated
reader pages retain existing finder cache-version URLs.

## Verification

- All 1,084 manuscript representations checked against the original Git snapshot:
  no source URL or numeric spelling lost; identity/status metadata unchanged.
- Every original Markdown destination preserved, including relative references.
- No remaining routine SIMBAD name in the narrative of those representations.
- Every recorded external source destination renders as an HTML anchor.
- `python tools/clean_story_sources.py --check`: 1,084 checked; zero edits needed.
- `python tools/test_fixed_object_stories.py`: eight tests passed.
- `python -m unittest discover -s tests -p 'test_luna*.py'`: twelve tests passed.
- Reviewed publisher dry run: four complete stories eligible; 52 pending stories
  retain pending status. Draft rendering does not grant research approval.
- `git diff --check`: passed.

## Remaining source research

Six older drafts (permanent object IDs 2, 4, 5, 9, 155 and 220) contain no recorded
source URLs. Their citations cannot be relocated or verified until sources are
researched. No citations or approvals were invented for them. This presentation
pass is not an accuracy audit, plagiarism audit, or live external-link availability
check; existing research/finder/publication review states remain authoritative.
